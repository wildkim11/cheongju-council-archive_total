"""Verify derived ledgers against source hashes and exact Markdown coordinates."""
import argparse,bisect,collections,gzip,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def digest(raw):return hashlib.sha256(raw).hexdigest()
def require(value,message):
 if not value:raise ValueError(message)
def verify(root=ROOT):
 root=Path(root);out=root/'exports/processing';manifest=json.loads((out/'manifest.json').read_text());require(manifest['schema']=='cheongju-processing-manifest/1','processing schema');require(manifest['processor_sha256']==digest((Path(__file__).parent/'process_meeting_segments.py').read_bytes()),'processing code version mismatch')
 inputs={}
 for name,meta in manifest['inputs'].items():
  raw=(root/'exports/analyzer'/f'{name}.jsonl').read_bytes();require(digest(raw)==meta['sha256'],'processing input changed: '+name);inputs[name]=[json.loads(x) for x in raw.splitlines()];require(len(inputs[name])==meta['rows'],'processing input rows')
 people={p['person_id']:p for p in inputs['people']};tenures=inputs['tenures'];source_rows=json.loads((root/'indexes/integrated/meetings.json').read_text());sources={r['meeting_id']:r for r in source_rows};require(len(sources)==len(source_rows),'source meeting IDs duplicate');require(digest((root/'indexes/integrated/meetings.json').read_bytes())==manifest['source_index_sha256'],'meeting index changed')
 packed=(out/manifest['activity_roles']['path']).read_bytes();require(digest(packed)==manifest['activity_roles']['sha256'],'activity ledger hash mismatch');ledger=[json.loads(x) for x in gzip.decompress(packed).splitlines()];requests=collections.defaultdict(list);links_checked=0
 for activity in ledger:
  if activity.get('source_link'):requests[activity['source_link']['segment_id']].append(activity)
 raw=(out/manifest['meeting_catalog']['path']).read_bytes();require(digest(raw)==manifest['meeting_catalog']['sha256'],'catalog hash mismatch');catalog=json.loads(raw);require({x['meeting_id'] for x in catalog}==set(sources) and len(catalog)==len(sources),'catalog coverage mismatch');counts=collections.Counter()
 for entry in catalog:
  row=sources[entry['meeting_id']];packed=(out/entry['path']).read_bytes();require(digest(packed)==entry['sha256'] and len(packed)==entry['bytes'],'segment shard hash/size mismatch');doc=json.loads(gzip.decompress(packed));require(doc['source_sha256']==row['sha256'] and doc['official_content_sha256']==row['content_sha256'],'shard source hash mismatch');require(doc['official_url']==row['official_url'] and doc['term']==row['term'] and doc['date']==row['date'],'meeting source metadata mismatch');require(doc['processor_sha256']==manifest['processor_sha256'] and doc['identity_fingerprint']==manifest['identity_fingerprint'],'shard processing context mismatch')
  source=(root/row['path']).read_bytes();require(digest(source)==row['sha256'],'original changed');text=source.decode('utf-8');pieces=text.split('\n\n',2);cursor=len(pieces[0])+len(pieces[1])+4;segs=doc['segments'];line_starts=[0]+[i+1 for i,c in enumerate(text) if c=='\n'];ids=set();paragraph_count=0
  for s in segs:
   start,end=s['char_start'],s['char_end'];require(start==cursor and start<end<=len(text),'segment range coverage mismatch');cursor=end;sid=s['segment_id'];require(sid not in ids and sid.startswith(row['meeting_id']+'@'+row['sha256'][:12]+':s'),'segment ID mismatch');ids.add(sid);require(s['line_start']==bisect.bisect_right(line_starts,start) and s['line_end']==bisect.bisect_right(line_starts,end-1),'segment line coordinates mismatch');require(start<=s['content_start']<=end,'content range mismatch')
   if s['kind']=='speech':
    header=text[start:end].split('\n',1)[0];require(s['speaker_name'] in header and s['speaker_role'] in header,'speaker fields absent from source header');require(s['speech_function']=='unclassified','unsupported speech-function inference')
    if s['person_id']:
     p=people.get(s['person_id']);require(p and p['name']==s['speaker_name'],'speaker identity name mismatch');require(any(t['person_id']==s['person_id'] and t['term']==row['term'] and t['council_scope']==row['council_scope'] for t in tenures),'speaker identity term mismatch');require(s['speaker_category'].startswith('council_'),'non-council speaker assigned to member')
    if s['identity_status']=='resolved_source_meeting_term':require(s.get('tenure_interval_verified') is False,'term evidence misreported as exact dates')
   for activity in requests.get(sid,[]):
    proof=activity['source_link'];source=inputs[activity['source_dataset']][activity['source_row_1based']-1];needle=re.sub(r'\s+',' ',source.get('body_text') or '').strip();haystack=re.sub(r'\s+',' ',text[s['content_start']:end]).strip()
    method=proof.get('method','entire_activity_body_exact_normalized_substring')
    if method=='entire_activity_body_exact_spacing_compacted_digit_boundaries':
     def independent_spacing(value):
      parts=re.split(r'(\s+)',value)
      return ''.join((' ' if i>0 and i+1<len(parts) and parts[i-1] and parts[i+1] and parts[i-1][-1].isdecimal() and parts[i+1][0].isdecimal() else '') if part.isspace() else part for i,part in enumerate(parts))
     needle=independent_spacing(source.get('body_text') or '');haystack=independent_spacing(text[s['content_start']:end])
     require(digest((source.get('body_text') or '').encode())==proof.get('activity_body_sha256'),'activity original body hash mismatch')
     post=manifest.get('activity_spacing_postprocessor',{});require(post.get('method')==method and post.get('script_sha256')==digest((Path(__file__).parent/'resolve_activity_spacing_matches.py').read_bytes()),'spacing postprocessor version mismatch')
    else:require(method=='entire_activity_body_exact_normalized_substring','unsupported cross-source match method')
    require(len(needle)>=80 and source['date']==row['date'] and source.get('council_scope')==row['council_scope'] and activity['person_name']==s.get('speaker_name'),'cross-source match scope mismatch');require(proof['meeting_id']==row['meeting_id'] and proof['source_sha256']==row['sha256'] and activity['person_id']==s.get('person_id'),'cross-source identity mismatch');require(digest(needle.encode())==proof['normalized_body_sha256'] and haystack[proof['normalized_start']:proof['normalized_end']]==needle,'cross-source full body mismatch');links_checked+=1
   previous=s['content_start'];pids=set()
   for para in s['paragraphs']:
    a,b=para['char_start'],para['char_end'];require(previous<=a<b<=end,'paragraph range mismatch');previous=b;require(para['paragraph_id'] not in pids and para['paragraph_id'].startswith(sid+':p'),'paragraph ID mismatch');pids.add(para['paragraph_id']);require(digest(text[a:b].encode())==para['text_sha256'],'paragraph text hash mismatch');require(para['line_start']==bisect.bisect_right(line_starts,a) and para['line_end']==bisect.bisect_right(line_starts,b-1),'paragraph line mismatch');paragraph_count+=1
  require(cursor==len(text) and len(segs)==entry['segments'] and paragraph_count==entry['paragraphs'],'source tail/count mismatch');counts.update(segments=len(segs),paragraphs=paragraph_count,meetings=1)
 ids=set();records=0
 for r in ledger:
  require(r['activity_id'] not in ids,'duplicate activity role');ids.add(r['activity_id']);dataset=r['source_dataset'];n=r['source_row_1based'];require(1<=n<=len(inputs[dataset]),'source activity row absent');source=inputs[dataset][n-1];name=source.get('person_name') or source.get('speaker_name');url=source.get('source_url') or source.get('official_url') or source.get('detail_url');require(r['person_name']==name and r['official_url']==url,'activity evidence mismatch')
  if r['person_id']:require(people.get(r['person_id'],{}).get('name')==name,'activity person mismatch')
  if dataset=='bill_proposers_member_only':require(r['role']==source['proposer_role'] and r['person_id']==source['person_id'],'bill role mismatch')
  records+=1
 require(links_checked==sum(len(v) for v in requests.values()),'cross-source evidence absent from segment corpus');require(records==manifest['activity_roles']['rows'],'activity role count mismatch');require(counts['segments']==manifest['segments']['segments'] and counts['paragraphs']==manifest['segments']['paragraphs'],'manifest totals mismatch')
 return {'status':'PASS',**counts,'activity_role_rows':records,'exact_body_links_verified':links_checked,'verified_originals':len(sources),'official_site_requests':0,'analysis_classification_complete':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out',type=Path);a=p.parse_args();result=verify(a.root)
 if a.out:a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False,indent=2))
