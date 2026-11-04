"""Derive exact question/answer parts; never promote identities or alter raw data."""
from __future__ import annotations
import argparse,collections,gzip,json,re
from pathlib import Path
from process_meeting_segments import sha,load_export,write_json
from resolve_activity_spacing_matches import compact
ROOT=Path(__file__).resolve().parents[1]
def split_candidate(body,question,answer):
 """Require a complete question prefix and a complete unique executive tail."""
 a=compact(body);q=compact(question)
 if len(q)<80 or not a.startswith(q):return None
 tail=a[len(q):]
 if len(tail)<80 or compact(answer).count(tail)!=1:return None
 # Map normalized question end back to the original text without changing it.
 positions=[];last=0
 for m in re.finditer(r'\s+',body):
  positions.extend(range(last,m.start()))
  if m.start()>0 and m.end()<len(body)and body[m.start()-1].isdecimal()and body[m.end()].isdecimal():positions.append(m.start())
  last=m.end()
 positions.extend(range(last,len(body)));assert len(positions)==len(a)
 boundary=positions[len(q)-1]+1;question_raw=body[:boundary];answer_raw=body[boundary:]
 if compact(question_raw)!=q or compact(answer_raw)!=tail:raise ValueError('split boundary mismatch')
 return {'question_text':question_raw,'answer_text':answer_raw,'question_char_end':boundary,'answer_normalized_start':compact(answer).find(tail),'answer_normalized_end':compact(answer).find(tail)+len(tail)}
def build(root=ROOT):
 root=Path(root);out=root/'exports/processing';pm=json.loads((out/'manifest.json').read_text());mf=json.loads((root/'exports/analyzer/manifest.json').read_text());data=load_export(root,'city_questions',mf)
 idxraw=(root/'indexes/integrated/meetings.json').read_bytes();catraw=(out/'meeting_segments_catalog.json').read_bytes()
 if sha(idxraw)!=pm['source_index_sha256']or sha(catraw)!=pm['meeting_catalog']['sha256']:raise ValueError('question split index/catalog hash mismatch')
 sources={m['meeting_id']:m for m in json.loads(idxraw)};catalog=json.loads(catraw);days=collections.defaultdict(list);cache={}
 for e in catalog:days[(sources[e['meeting_id']]['council_scope'],sources[e['meeting_id']]['date'])].append(e)
 def doc(e):
  key=e['meeting_id']
  if key not in cache:
   m=sources[key];raw=(root/m['path']).read_bytes();packed=(out/e['path']).read_bytes()
   if sha(raw)!=m['sha256']or sha(packed)!=e['sha256']:raise ValueError('question split source/shard hash mismatch')
   d=json.loads(gzip.decompress(packed))
   if d['source_sha256']!=m['sha256']or d['date']!=m['date']or d['term']!=m['term']:raise ValueError('question split context mismatch')
   cache[key]=(raw.decode(),d)
  return cache[key]
 rows=[]
 for i,src in enumerate(data,1):
  body=src.get('body_text')or'';matches=[]
  for e in days[(src['council_scope'],src['date'])]:
   text,d=doc(e);m=sources[e['meeting_id']]
   questions=[s for s in d['segments']if s.get('speaker_name')==src['speaker_name']and s.get('speaker_category','').startswith('council_')and s.get('person_id')]
   answers=[s for s in d['segments']if s.get('speaker_category')=='executive_or_staff']
   for q in questions:
    qt=text[q['content_start']:q['char_end']]
    if len(compact(qt))<80 or not compact(body).startswith(compact(qt)):continue
    for ans in answers:
     if ans['content_start']<=q['char_end']:continue
     result=split_candidate(body,qt,text[ans['content_start']:ans['char_end']])
     if result:matches.append({**result,'meeting_id':m['meeting_id'],'meeting_url':m['official_url'],'source_path':m['path'],'source_sha256':m['sha256'],'question_segment_id':q['segment_id'],'question_speaker_name':q['speaker_name'],'question_candidate_person_id':q['person_id'],'answer_segment_id':ans['segment_id'],'answer_speaker_name':ans['speaker_name'],'answer_speaker_category':ans['speaker_category'],'question_line_start':q['line_start'],'question_line_end':q['line_end'],'answer_line_start':ans['line_start'],'answer_line_end':ans['line_end']})
  rows.append({'activity_id':f"city_questions:{src['source_id']}:speaker",'source_row_1based':i,'date':src['date'],'person_name':src['speaker_name'],'activity_url':src.get('official_url')or src.get('detail_url'),'activity_body_sha256':sha(body.encode()),'status':'verified_unique_question_answer_split'if len(matches)==1 else'ambiguous_question_answer_split'if matches else'unverified_question_answer_boundary','question_text_boundary_verified':len(matches)==1,'member_analysis_requires_activity_gate':True,'answer_attribution_to_member_allowed':False,'identity_promotion_allowed':False,'candidates':matches})
 report={'schema':'cheongju-question-answer-parts/1','status':'PASS','source_dataset_sha256':mf['datasets']['city_questions']['sha256'],'source_index_sha256':sha(idxraw),'reviewed_records':len(data),'split_records':sum(r['question_text_boundary_verified']for r in rows),'ambiguous_records':sum(len(r['candidates'])>1 for r in rows),'unverified_records':sum(not r['candidates']for r in rows),'identity_promotions':0,'date_changes':0,'official_site_requests':0,'script_sha256':sha(Path(__file__).read_bytes()),'rows':rows}
 write_json(out/'question_answer_parts.json',report);summary={k:v for k,v in report.items()if k!='rows'};write_json(root/'reports/question-answer-parts-latest.json',summary);return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(build(a.root),ensure_ascii=False,indent=2))
