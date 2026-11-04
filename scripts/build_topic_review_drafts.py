"""Check archived AI coding proposals without treating them as human references."""
from __future__ import annotations
import argparse,collections,gzip,json
from pathlib import Path
from process_meeting_segments import sha,encoded,pack,write_json
from build_topic_review_materials import validate_topic_evidence
ROOT=Path(__file__).resolve().parents[1]
def validate_draft(a,record,book,book_hash):
 if a.get('schema')!='cheongju-topic-annotation-draft/1'or a.get('review_origin')!='automated'or a.get('status')!='draft'or a.get('reviewer_id')is not None or a.get('human_review_required')is not True or a.get('human_review_status')!='pending'or a.get('evaluation_reference_eligible')is not False or a.get('topic_set_complete')is not False or not a.get('reading_scope')or not a.get('generator')or not a.get('annotation_id'):raise ValueError('AI draft provenance/status mismatch')
 validate_topic_evidence(a,record,book,book_hash)
 return True

def build(root=ROOT,codebook_path=None):
 root=Path(root);out=root/'exports/topic-review';bookraw=(Path(codebook_path)if codebook_path else root/'config/policy_topics_v1.json').read_bytes();book=json.loads(bookraw);book_hash=sha(bookraw);tm=json.loads((out/'manifest.json').read_text());mf=json.loads((root/'exports/processing/member_text_inputs_manifest.json').read_text());meta=mf['outputs']['eligible'];raw=(root/'exports/processing'/meta['file']).read_bytes()
 if sha(raw)!=meta['sha256']or meta['sha256']!=tm['source_text_sha256']or tm['codebook_sha256']!=book_hash:raise ValueError('draft review input snapshot mismatch')
 records={r['activity_id']:r for r in map(json.loads,gzip.decompress(raw).splitlines())}
 taskmeta=tm['outputs']['review_tasks'];taskraw=(out/taskmeta['file']).read_bytes()
 if sha(taskraw)!=taskmeta['sha256']:raise ValueError('draft review task hash mismatch')
 tasks={r['activity_id']:r for r in map(json.loads,gzip.decompress(taskraw).splitlines())};valid=[];held=[];sources=[]
 for path in sorted((root/'archive/analysis_annotations').glob('*/ai_draft_*.jsonl')):
  source=path.read_bytes();sources.append({'path':str(path.relative_to(root)),'sha256':sha(source)})
  for line in source.splitlines():
   a=json.loads(line);aid=a.get('activity_id');record=records.get(aid);task=tasks.get(aid)
   try:
    if record is None or task is None:raise ValueError('source activity no longer eligible')
    if task['case_id']!=a.get('case_id'):raise ValueError('stale or altered review case')
    validate_draft(a,record,book,book_hash)
    valid.append({**a,'person_id':record['person_id'],'person_name':record['person_name'],'date':record['date'],'term':record['term'],'activity_url':record['activity_url'],'source_content_proofs':record['source_content_proofs']})
   except ValueError as error:held.append({'annotation_id':a.get('annotation_id'),'activity_id':aid,'hold_reason':str(error),'archive_path':str(path.relative_to(root))})
 duplicates=collections.Counter(a['case_id']for a in valid);unique=[]
 for a in valid:
  if duplicates[a['case_id']]>1:held.append({'annotation_id':a['annotation_id'],'activity_id':a['activity_id'],'hold_reason':'duplicate current AI proposals require explicit resolution'})
  else:unique.append(a)
 outputs={}
 for label,rows in [('draft_review',unique),('draft_review_held',held)]:
  payload=pack(b''.join(encoded(r)for r in rows));filename=label+'.jsonl.gz';(out/filename).write_bytes(payload);outputs[label]={'file':filename,'rows':len(rows),'sha256':sha(payload),'bytes':len(payload)}
 manifest={'schema':'cheongju-topic-draft-review-release/1','script_sha256':sha(Path(__file__).read_bytes()),'source_task_manifest_sha256':sha((out/'manifest.json').read_bytes()),'codebook_sha256':book_hash,'archive_sources':sources,'outputs':outputs};write_json(out/'draft_manifest.json',manifest)
 report={'schema':'cheongju-topic-draft-review/1','status':'PASS','archived_draft_records':len(unique)+len(held),'source_integrity_valid_drafts':len(unique),'held_drafts':len(held),'evidence_spans_verified':sum(len(a['evidence_spans'])for a in unique),'human_reviews_completed':0,'confirmed_topic_assignments':0,'semantic_validation_complete':False,'accuracy_computed':False,'interest_scores_computed':0,'official_site_requests':0,'reading_scope':'selected_policy_passages_with_context; full independent human review still required'};write_json(root/'reports/topic-draft-review-latest.json',report);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(build(a.root),ensure_ascii=False,indent=2))
