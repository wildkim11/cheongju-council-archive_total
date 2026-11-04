"""Preserve single-edit activity evidence without fuzzy identity promotion."""
from __future__ import annotations
import argparse,collections,difflib,gzip,json,re,unicodedata
from pathlib import Path
from process_meeting_segments import sha,load_export,write_json
from resolve_activity_spacing_matches import compact
ROOT=Path(__file__).resolve().parents[1]
NOTES={'…….(발언제한시간초과로마이크중단)(마이크중단이후발언한부분)','(발언제한시간초과로마이크중단)(마이크중단이후발언한부분)'}
def classify(a,b,edge=False,dataset='five_minute_speeches'):
 if dataset=='city_questions'and edge and a and not b:return 'question_answer_tail_review'
 if not a and b in NOTES:return 'recording_stage_note'
 if not a and re.fullmatch(r'\([A-Za-z]+\)',b):return 'parenthesized_latin_annotation'
 if b=='○○'and a:return 'redacted_person_name'
 if {a,b}=={'%','프로'}:return 'percentage_notation'
 if (a==' 'and not b)or(b==' 'and not a):return 'numeric_whitespace_boundary'
 if a+b and all(unicodedata.category(c)[0]not in 'LN'for c in a+b)or {a,b}<=set(['․','ㆍ',',']):return 'symbol_or_middle_dot'
 return 'word_or_particle_difference'
def review(root=ROOT):
 root=Path(root);out=root/'exports/processing';pm=json.loads((out/'manifest.json').read_text());mf=json.loads((root/'exports/analyzer/manifest.json').read_text());data={n:load_export(root,n,mf)for n in ['five_minute_speeches','city_questions']}
 raw=(out/'activity_roles.jsonl.gz').read_bytes();idxraw=(root/'indexes/integrated/meetings.json').read_bytes();catraw=(out/'meeting_segments_catalog.json').read_bytes()
 if sha(raw)!=pm['activity_roles']['sha256']or sha(idxraw)!=pm['source_index_sha256']or sha(catraw)!=pm['meeting_catalog']['sha256']:raise ValueError('single difference input hash mismatch')
 sources={m['meeting_id']:m for m in json.loads(idxraw)};targets=collections.defaultdict(list);found=collections.defaultdict(list)
 for a in map(json.loads,gzip.decompress(raw).splitlines()):
  if not a.get('person_id')and a['source_dataset']in data:targets[a['date']].append(a)
 for e in json.loads(catraw):
  m=sources[e['meeting_id']]
  if m['date']not in targets:continue
  source=(root/m['path']).read_bytes();packed=(out/e['path']).read_bytes()
  if sha(source)!=m['sha256']or sha(packed)!=e['sha256']:raise ValueError('single difference source/shard hash mismatch')
  doc=json.loads(gzip.decompress(packed));text=source.decode()
  if doc['source_sha256']!=m['sha256']or doc['date']!=m['date']or doc['term']!=m['term']:raise ValueError('single difference source context mismatch')
  for a in targets[m['date']]:
   src=data[a['source_dataset']][a['source_row_1based']-1]
   if src['council_scope']!=m['council_scope']:continue
   for s in doc['segments']:
    if s.get('speaker_name')!=a['person_name']or not s.get('speaker_category','').startswith('council_')or not s.get('person_id'):continue
    if a.get('candidate_person_ids')and s['person_id']not in a['candidate_person_ids']:continue
    found[a['activity_id']].append((a,src,m,s,text[s['content_start']:s['char_end']]))
 rows=[]
 for matches in found.values():
  if len(matches)!=1:continue
  a,src,m,s,speech=matches[0];body=src.get('body_text')or'';left=compact(body);right=compact(speech)
  strip=lambda t:''.join(c for c in t if not unicodedata.category(c).startswith('P'))
  if len(left)<80 or (len(strip(left))>=80 and strip(left)in strip(right)):continue
  ops=difflib.SequenceMatcher(None,left,right,autojunk=False).get_opcodes();changes=[o for o in ops if o[0]!='equal']
  if len(changes)!=1:continue
  tag,i,j,k,l=changes[0];assert ''.join(left[x:y]for _,x,y,_,_ in ops)==left and ''.join(right[x:y]for _,_,_,x,y in ops)==right
  x,y=left[i:j],right[k:l];edge=i==0 or j==len(left)
  rows.append({'activity_id':a['activity_id'],'person_name':a['person_name'],'date':a['date'],'activity_url':a['official_url'],'activity_body_sha256':sha(body.encode()),'activity_original_body':body,'meeting_id':m['meeting_id'],'meeting_url':m['official_url'],'source_path':m['path'],'source_sha256':m['sha256'],'segment_id':s['segment_id'],'minutes_original_speech':speech,'operation':tag,'activity_start':i,'activity_end':j,'minutes_start':k,'minutes_end':l,'activity_difference':x,'minutes_difference':y,'activity_context':left[max(0,i-40):min(len(left),j+40)],'minutes_context':right[max(0,k-40):min(len(right),l+40)],'classification':classify(x,y,edge,a['source_dataset']),'automatic_identity_promotion_allowed':False,'automatic_source_correction_allowed':False})
 report={'schema':'cheongju-single-activity-difference-review/1','status':'PASS','review_rows':len(rows),'classification_counts':dict(collections.Counter(r['classification']for r in rows)),'source_roles_sha256':sha(raw),'source_index_sha256':sha(idxraw),'script_sha256':sha(Path(__file__).read_bytes()),'identity_promotions':0,'date_changes':0,'official_site_requests':0,'rows':rows};write_json(root/'reports/activity-single-differences.json',report);return{k:v for k,v in report.items()if k!='rows'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(review(a.root),ensure_ascii=False,indent=2))
