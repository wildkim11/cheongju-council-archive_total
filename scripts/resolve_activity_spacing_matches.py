"""Link full activity text with spacing differences; preserve all non-space chars.

A unique same-date/name council speech is required. Numeric separators between
adjacent decimal digits survive normalization. No fuzzy or partial-body matching.
"""
from __future__ import annotations
import argparse,collections,gzip,json,re
from pathlib import Path
from process_meeting_segments import sha,encoded,pack,write_json,load_export
ROOT=Path(__file__).resolve().parents[1]
METHOD='entire_activity_body_exact_spacing_compacted_digit_boundaries'
def compact(text):
 return re.sub(r'\s+',lambda m:' 'if m.start()>0 and m.end()<len(text)and text[m.start()-1].isdecimal()and text[m.end()].isdecimal()else'',text)
def match(body,speech):
 needle=compact(body)
 if len(needle)<80:return None
 hay=compact(speech);start=hay.find(needle)
 if start<0:return None
 return {'normalized_body_sha256':sha(needle.encode()),'normalized_start':start,'normalized_end':start+len(needle),'activity_body_sha256':sha(body.encode()),'method':METHOD}
def resolve(root=ROOT):
 root=Path(root);out=root/'exports/processing';pm=json.loads((out/'manifest.json').read_text());mf=json.loads((root/'exports/analyzer/manifest.json').read_text());names=('five_minute_speeches','city_questions');data={n:load_export(root,n,mf)for n in names};raw=(out/'activity_roles.jsonl.gz').read_bytes()
 if sha(raw)!=pm['activity_roles']['sha256']:raise ValueError('activity role input hash mismatch')
 ledger=[json.loads(l)for l in gzip.decompress(raw).splitlines()];targets=collections.defaultdict(list);state={}
 for row in ledger:
  if row.get('person_id')or row['source_dataset']not in names or row['identity_status']!='candidate_missing_dated_tenure':continue
  src=data[row['source_dataset']][row['source_row_1based']-1];body=src.get('body_text')or'';aid=row['activity_id'];state[aid]={'activity_id':aid,'source_dataset':row['source_dataset'],'source_row_1based':row['source_row_1based'],'date':row['date'],'person_name':row['person_name'],'body_chars':len(body),'matching_body_chars':len(compact(body)),'same_date_meetings':0,'same_speaker_segments':0,'resolved_speaker_segments':0,'matches':[]}
  if len(compact(body))>=80:targets[row['date']].append((row,body,src.get('council_scope')))
 index_raw=(root/'indexes/integrated/meetings.json').read_bytes()
 if sha(index_raw)!=pm['source_index_sha256']:raise ValueError('meeting index input changed')
 sources={m['meeting_id']:m for m in json.loads(index_raw)};catalog_raw=(out/'meeting_segments_catalog.json').read_bytes()
 if sha(catalog_raw)!=pm['meeting_catalog']['sha256']:raise ValueError('segment catalog input changed')
 for entry in json.loads(catalog_raw):
  m=sources[entry['meeting_id']]
  if m['date']not in targets:continue
  packed=(out/entry['path']).read_bytes();source=(root/m['path']).read_bytes()
  if sha(packed)!=entry['sha256']or sha(source)!=m['sha256']:raise ValueError('source/shard hash mismatch')
  doc=json.loads(gzip.decompress(packed));text=source.decode()
  if doc['date']!=m['date']or doc['term']!=m['term']or doc['source_sha256']!=m['sha256']:raise ValueError('segment context mismatch')
  for row,body,scope in targets[m['date']]:
   if scope!=m['council_scope']:continue
   item=state[row['activity_id']];item['same_date_meetings']+=1
   for seg in doc['segments']:
    if seg.get('speaker_name')!=row['person_name']or not seg.get('speaker_category','').startswith('council_'):continue
    item['same_speaker_segments']+=1
    if not seg.get('person_id'):continue
    item['resolved_speaker_segments']+=1
    if row.get('candidate_person_ids')and seg['person_id']not in row['candidate_person_ids']:continue
    proof=match(body,text[seg['content_start']:seg['char_end']])
    if proof:item['matches'].append({**proof,'meeting_id':m['meeting_id'],'segment_id':seg['segment_id'],'person_id':seg['person_id'],'term':m['term'],'source_sha256':m['sha256']})
 inverse=collections.Counter()
 for row in ledger:
  item=state.get(row['activity_id']);proofs=item['matches']if item else []
  proof=proofs[0]if len(proofs)==1 else row.get('source_link')
  if proof:
   normal_hash=sha(compact(data[row['source_dataset']][row['source_row_1based']-1].get('body_text')or'').encode())if row['source_dataset']in data else proof['normalized_body_sha256']
   inverse[(row['source_dataset'],proof['segment_id'],normal_hash)]+=1
 added=0;reasons=collections.Counter()
 for row in ledger:
  if row['activity_id']not in state:continue
  item=state[row['activity_id']];proofs=item['matches']
  if len(proofs)==1 and inverse[(row['source_dataset'],proofs[0]['segment_id'],proofs[0]['normalized_body_sha256'])]==1:
   proof=proofs[0];row.update(person_id=proof['person_id'],candidate_person_ids=[],identity_status='resolved_cross_source_exact_body',resolved_term=proof['term'],term=proof['term'],tenure_interval_verified=False,source_link=proof);added+=1;status='resolved_unique_complete_spacing_match'
  else:status='duplicate_complete_activity_body'if len(proofs)==1 else 'body_missing_or_short'if item['matching_body_chars']<80 else 'no_same_date_meeting'if not item['same_date_meetings']else 'no_same_speaker_segment'if not item['same_speaker_segments']else 'speaker_not_resolved'if not item['resolved_speaker_segments']else 'ambiguous_complete_matches'if len(proofs)>1 else 'different_body_or_punctuation'
  item['status']=status;reasons[status]+=1
 payload=pack(b''.join(encoded(r)for r in ledger));meta=pm['activity_roles'];meta.update(sha256=sha(payload),bytes=len(payload),source_linked_rows=sum(bool(r.get('source_link'))for r in ledger),identity_status=dict(collections.Counter(r['identity_status']for r in ledger)))
 pm['activity_spacing_postprocessor']={'schema':'activity-spacing-links/1','script_sha256':sha(Path(__file__).read_bytes()),'method':METHOD,'input_activity_roles_sha256':sha(raw),'added_links':added,'method_linked_rows':sum(r.get('source_link',{}).get('method')==METHOD for r in ledger)}
 (out/'activity_roles.jsonl.gz').write_bytes(payload);write_json(out/'manifest.json',pm)
 processing_report=root/'reports/processing-latest.json'
 if processing_report.exists():
  previous=json.loads(processing_report.read_text());previous.update(manifest_sha256=sha((out/'manifest.json').read_bytes()),activity_spacing_added_links=added);write_json(processing_report,previous)
 report={'status':'PASS','method':METHOD,'added_links':added,'diagnosis_counts':dict(reasons),'source_linked_rows':meta['source_linked_rows'],'unassigned_rows':sum(not r.get('person_id')for r in ledger),'official_site_requests':0,'unassigned_written_questions_requiring_attachment_evidence':sum(not r.get('person_id')and r['source_dataset']=='written_questions'for r in ledger),'rows':list(state.values())};write_json(root/'reports/activity-spacing-link-review.json',report);return {k:v for k,v in report.items()if k!='rows'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(resolve(a.root),ensure_ascii=False,indent=2))
