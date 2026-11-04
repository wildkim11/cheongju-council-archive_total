"""Audit split-question identity candidates; do not promote activity attribution."""
from __future__ import annotations
import argparse,collections,gzip,json
from pathlib import Path
from process_meeting_segments import sha,load_export,write_json
from build_question_answer_parts import split_candidate
ROOT=Path(__file__).resolve().parents[1]
def assess(role,part,meeting,person,tenures):
 c=part['candidates'][0];pid=c['question_candidate_person_id'];reasons=[]
 if person.get('person_id')!=pid or person.get('name')!=role['person_name']or c['question_speaker_name']!=role['person_name']:reasons.append('person_or_name_mismatch')
 if pid not in role.get('candidate_person_ids',[])and pid!=role.get('person_id'):reasons.append('outside_existing_identity_candidates')
 if part['date']!=role['date']or meeting['date']!=role['date']:reasons.append('date_mismatch')
 matches=[t for t in tenures if t['person_id']==pid and t['term']==meeting['term']and t['council_scope']==meeting['council_scope']]
 if not matches:reasons.append('missing_person_scope_term_record')
 return reasons

def review(root=ROOT):
 root=Path(root);out=root/'exports/processing';mf=json.loads((root/'exports/analyzer/manifest.json').read_text());pm=json.loads((out/'manifest.json').read_text());parts=json.loads((out/'question_answer_parts.json').read_text());people={p['person_id']:p for p in load_export(root,'people',mf)};tenures=load_export(root,'tenures',mf);sources=load_export(root,'city_questions',mf)
 raw=(out/'activity_roles.jsonl.gz').read_bytes();idx=(root/'indexes/integrated/meetings.json').read_bytes();cat=(out/'meeting_segments_catalog.json').read_bytes()
 if sha(raw)!=pm['activity_roles']['sha256']or sha(idx)!=pm['source_index_sha256']or sha(cat)!=pm['meeting_catalog']['sha256']or parts['source_index_sha256']!=sha(idx)or parts['source_dataset_sha256']!=mf['datasets']['city_questions']['sha256']:raise ValueError('question identity snapshot mismatch')
 roles={r['activity_id']:r for r in map(json.loads,gzip.decompress(raw).splitlines())};meetings={m['meeting_id']:m for m in json.loads(idx)};catalog={e['meeting_id']:e for e in json.loads(cat)};rows=[]
 for part in parts['rows']:
  if not part['question_text_boundary_verified']:continue
  if len(part['candidates'])!=1:raise ValueError('non-unique split evidence')
  role=roles[part['activity_id']];c=part['candidates'][0];meeting=meetings[c['meeting_id']];e=catalog[c['meeting_id']];source=(root/meeting['path']).read_bytes();packed=(out/e['path']).read_bytes()
  if sha(source)!=meeting['sha256']or sha(packed)!=e['sha256']or c['source_sha256']!=meeting['sha256']:raise ValueError('question identity source hash mismatch')
  doc=json.loads(gzip.decompress(packed));segs={s['segment_id']:s for s in doc['segments']};q=segs[c['question_segment_id']];a=segs[c['answer_segment_id']];src=sources[part['source_row_1based']-1];body=src.get('body_text')or'';text=source.decode()
  if src['speaker_name']!=role['person_name']or q['speaker_name']!=role['person_name']or src['source_id']!=part['activity_id'].split(':')[1]or src['council_scope']!=meeting['council_scope']or q['person_id']!=c['question_candidate_person_id']or not q['speaker_category'].startswith('council_')or a['speaker_category']!='executive_or_staff'or a['content_start']<=q['char_end']or sha(body.encode())!=part['activity_body_sha256']:raise ValueError('question identity source context mismatch')
  proof=split_candidate(body,text[q['content_start']:q['char_end']],text[a['content_start']:a['char_end']])
  if not proof or proof['question_text']!=c['question_text']or proof['answer_text']!=c['answer_text']:raise ValueError('question identity split mismatch')
  pid=c['question_candidate_person_id'];reasons=assess(role,part,meeting,people.get(pid,{}),tenures)
  rows.append({'activity_id':part['activity_id'],'person_name':role['person_name'],'date':role['date'],'meeting_id':meeting['meeting_id'],'meeting_term':meeting['term'],'candidate_person_id':pid,'existing_candidate_count':len(role.get('candidate_person_ids',[])),'status':'source_term_candidate_confirmed'if not reasons else'candidate_review_held','review_reasons':reasons,'exact_tenure_interval_verified':False,'existing_activity_identity_status':role['identity_status'],'activity_url':role['official_url'],'meeting_url':meeting['official_url'],'source_sha256':meeting['sha256'],'question_segment_id':q['segment_id'],'answer_segment_id':a['segment_id'],'answer_speaker_name':a['speaker_name'],'automatic_identity_promotion_allowed':False})
 report={'schema':'cheongju-question-identity-evidence-review/1','status':'PASS','review_rows':len(rows),'source_term_candidate_confirmed':sum(not r['review_reasons']for r in rows),'multiple_existing_candidates_narrowed':sum(not r['review_reasons']and r['existing_candidate_count']>1 for r in rows),'identity_promotions':0,'date_changes':0,'official_site_requests':0,'source_roles_sha256':sha(raw),'source_question_parts_sha256':sha((out/'question_answer_parts.json').read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),'rows':rows};write_json(root/'reports/question-identity-evidence-review.json',report);return{k:v for k,v in report.items()if k!='rows'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(review(a.root),ensure_ascii=False,indent=2))
