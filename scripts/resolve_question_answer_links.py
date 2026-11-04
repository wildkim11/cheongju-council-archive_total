"""Attribute only complete, source-verified questions with verified executive tails."""
from __future__ import annotations
import argparse,collections,gzip,json
from pathlib import Path
from process_meeting_segments import sha,encoded,pack,write_json
from resolve_activity_spacing_matches import compact
import review_question_identity_evidence
ROOT=Path(__file__).resolve().parents[1]
METHOD='complete_question_prefix_and_verified_executive_answer_tail'
def resolve(root=ROOT):
 root=Path(root);out=root/'exports/processing'
 # This audit reopens hashed originals and verifies both source speakers/parts.
 review_question_identity_evidence.review(root)
 audit=json.loads((root/'reports/question-identity-evidence-review.json').read_text());parts=json.loads((out/'question_answer_parts.json').read_text());pm=json.loads((out/'manifest.json').read_text());raw=(out/'activity_roles.jsonl.gz').read_bytes()
 if sha(raw)!=pm['activity_roles']['sha256']or sha(raw)!=audit['source_roles_sha256']:raise ValueError('question link role snapshot mismatch')
 ledger=[json.loads(l)for l in gzip.decompress(raw).splitlines()];by={r['activity_id']:r for r in ledger};splitby={r['activity_id']:r for r in parts['rows']};inverse=collections.Counter()
 for p in parts['rows']:
  if p['question_text_boundary_verified']and len(p['candidates'])==1:
   c=p['candidates'][0];inverse[(c['question_segment_id'],sha(compact(c['question_text']).encode()))]+=1
 added=[];held=[]
 for evidence in audit['rows']:
  aid=evidence['activity_id'];role=by[aid]
  if role.get('person_id'):continue
  if evidence['review_reasons']or role['identity_status']!='candidate_missing_dated_tenure':held.append(aid);continue
  p=splitby[aid];c=p['candidates'][0];q=compact(c['question_text']);answer=compact(c['answer_text'])
  if inverse[(c['question_segment_id'],sha(q.encode()))]!=1:held.append(aid);continue
  proof={'method':METHOD,'person_id':c['question_candidate_person_id'],'term':evidence['meeting_term'],'meeting_id':c['meeting_id'],'segment_id':c['question_segment_id'],'source_sha256':c['source_sha256'],'activity_body_sha256':p['activity_body_sha256'],'normalized_body_sha256':sha(q.encode()),'normalized_start':0,'normalized_end':len(q),'question_char_end':c['question_char_end'],'question_original_sha256':sha(c['question_text'].encode()),'answer_original_sha256':sha(c['answer_text'].encode()),'answer_body_sha256':sha(answer.encode()),'answer_segment_id':c['answer_segment_id'],'answer_normalized_start':c['answer_normalized_start'],'answer_normalized_end':c['answer_normalized_end']}
  role.update(person_id=proof['person_id'],candidate_person_ids=[],identity_status='resolved_cross_source_question_answer',resolved_term=proof['term'],term=proof['term'],tenure_interval_verified=False,source_link=proof);added.append(aid)
 payload=pack(b''.join(encoded(r)for r in ledger));pm['activity_roles'].update(sha256=sha(payload),bytes=len(payload),source_linked_rows=sum(bool(r.get('source_link'))for r in ledger),identity_status=dict(collections.Counter(r['identity_status']for r in ledger)))
 pm['activity_question_postprocessor']={'method':METHOD,'script_sha256':sha(Path(__file__).read_bytes()),'input_activity_roles_sha256':sha(raw),'added_links':len(added),'method_linked_rows':sum(r.get('source_link',{}).get('method')==METHOD for r in ledger)}
 (out/'activity_roles.jsonl.gz').write_bytes(payload);write_json(out/'manifest.json',pm)
 prior=root/'reports/processing-latest.json'
 if prior.exists():
  report=json.loads(prior.read_text());report.update(manifest_sha256=sha((out/'manifest.json').read_bytes()),activity_question_added_links=len(added));write_json(prior,report)
 report={'schema':'cheongju-question-answer-links/1','status':'PASS','method':METHOD,'added_links':len(added),'added_activity_ids':added,'held_activity_ids':held,'exact_tenure_intervals_added':0,'date_changes':0,'official_site_requests':0};write_json(root/'reports/question-answer-links-latest.json',report);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(resolve(a.root),ensure_ascii=False,indent=2))
