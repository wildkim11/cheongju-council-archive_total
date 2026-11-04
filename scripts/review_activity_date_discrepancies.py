"""Review full-body cross-date evidence without changing identities or dates."""
from __future__ import annotations
import argparse,collections,gzip,json
from pathlib import Path
from process_meeting_segments import sha,load_export,write_json
from resolve_activity_spacing_matches import match
ROOT=Path(__file__).resolve().parents[1]
NAMES=('five_minute_speeches','city_questions')
def candidate(activity,source,meeting,segment,text):
 if source.get('council_scope')!=meeting['council_scope']or activity['date']==meeting['date']:return None
 if segment.get('speaker_name')!=activity['person_name']or not segment.get('speaker_category','').startswith('council_')or not segment.get('person_id'):return None
 if activity.get('candidate_person_ids')and segment['person_id']not in activity['candidate_person_ids']:return None
 proof=match(source.get('body_text')or'',text[segment['content_start']:segment['char_end']])
 if not proof:return None
 return {**proof,'meeting_id':meeting['meeting_id'],'meeting_date':meeting['date'],'meeting_official_url':meeting['official_url'],'source_path':meeting['path'],'source_sha256':meeting['sha256'],'segment_id':segment['segment_id'],'segment_line_start':segment['line_start'],'segment_line_end':segment['line_end'],'candidate_person_id':segment['person_id'],'candidate_term':meeting['term']}
def review(root=ROOT):
 root=Path(root);out=root/'exports/processing';mf=json.loads((root/'exports/analyzer/manifest.json').read_text());pm=json.loads((out/'manifest.json').read_text());data={n:load_export(root,n,mf)for n in NAMES};raw=(out/'activity_roles.jsonl.gz').read_bytes()
 if sha(raw)!=pm['activity_roles']['sha256']:raise ValueError('date review role input hash mismatch')
 idxraw=(root/'indexes/integrated/meetings.json').read_bytes()
 if sha(idxraw)!=pm['source_index_sha256']:raise ValueError('date review index mismatch')
 index={m['meeting_id']:m for m in json.loads(idxraw)};days={(m['council_scope'],m['date'])for m in index.values()};targets=collections.defaultdict(list);rows=[]
 for a in map(json.loads,gzip.decompress(raw).splitlines()):
  if a.get('person_id')or a['source_dataset']not in NAMES:continue
  source=data[a['source_dataset']][a['source_row_1based']-1]
  if (source['council_scope'],a['date'])in days:continue
  item={'activity_id':a['activity_id'],'source_dataset':a['source_dataset'],'source_row_1based':a['source_row_1based'],'person_name':a['person_name'],'source_display_date':a['date'],'source_display_date_semantics':'unconfirmed','activity_official_url':a['official_url'],'activity_body_sha256':sha((source.get('body_text')or'').encode()),'candidates':[]};rows.append(item);targets[a['person_name']].append((a,source,item))
 catalog_raw=(out/'meeting_segments_catalog.json').read_bytes()
 if sha(catalog_raw)!=pm['meeting_catalog']['sha256']:raise ValueError('date review catalog mismatch')
 if targets:
  for entry in json.loads(catalog_raw):
   packed=(out/entry['path']).read_bytes()
   if sha(packed)!=entry['sha256']:raise ValueError('date review shard hash mismatch')
   doc=json.loads(gzip.decompress(packed));segments=[s for s in doc['segments']if s.get('speaker_name')in targets]
   if not segments:continue
   meeting=index[entry['meeting_id']];source_bytes=(root/meeting['path']).read_bytes()
   if sha(source_bytes)!=meeting['sha256']or doc['source_sha256']!=meeting['sha256']or doc['date']!=meeting['date']or doc['term']!=meeting['term']:raise ValueError('date review source context mismatch')
   text=source_bytes.decode()
   for seg in segments:
    for a,source,item in targets[seg['speaker_name']]:
     proof=candidate(a,source,meeting,seg,text)
     if proof:item['candidates'].append(proof)
 counts=collections.Counter()
 for item in rows:
  item['status']='unique_cross_date_complete_body_match_review'if len(item['candidates'])==1 else 'ambiguous_cross_date_matches'if item['candidates']else 'no_cross_date_complete_body_match';item['automatic_date_change_allowed']=False;item['automatic_identity_promotion_allowed']=False;counts[item['status']]+=1
 report={'status':'PASS','schema':'cheongju-activity-date-review/1','source_role_sha256':sha(raw),'source_index_sha256':sha(idxraw),'review_rows':len(rows),'diagnosis_counts':dict(counts),'date_changes':0,'identity_promotions':0,'official_site_requests':0,'rows':rows};write_json(root/'reports/activity-date-discrepancies.json',report);return {k:v for k,v in report.items()if k!='rows'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(review(a.root),ensure_ascii=False,indent=2))
