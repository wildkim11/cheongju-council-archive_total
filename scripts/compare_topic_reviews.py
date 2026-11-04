"""Compare independently supplied human reviews with AI drafts; never create gold labels."""
from __future__ import annotations
import argparse,gzip,json
from pathlib import Path
from build_topic_review_materials import validate_annotation
from process_meeting_segments import sha,write_json
ROOT=Path(__file__).resolve().parents[1]
def compare(reviews,tasks,records,drafts,book,book_hash):
 result=[];held=[];seen=set()
 for review in reviews:
  case=review.get('case_id');reviewer=review.get('reviewer_id');key=(case,reviewer)
  try:
   if key in seen:raise ValueError('duplicate reviewer/case; explicit revision resolution required')
   seen.add(key);task=tasks.get(case)
   if task is None:raise ValueError('unknown or stale review case')
   if review.get('full_text_read')is not True:raise ValueError('full text review not declared')
   if review.get('review_method')not in {'independent','ai_assisted'}:raise ValueError('review method missing')
   if not isinstance(review.get('reviewed_at'),str)or not review['reviewed_at'].strip():raise ValueError('review timestamp missing')
   validate_annotation(review,records[task['activity_id']],book,book_hash)
   draft=drafts.get(case);human=set(review['topic_ids']);ai=set(draft['topic_ids'])if draft else None
   changed=ai is not None and(human!=ai or review['decision']!=draft['decision'])
   if changed and not str(review.get('change_reason')or'').strip():raise ValueError('changed coding requires change reason')
   result.append({'case_id':case,'activity_id':task['activity_id'],'reviewer_id':reviewer,'review_method':review['review_method'],'comparison':'no_ai_draft'if ai is None else'disagreement'if changed else'agreement','human_topic_ids':sorted(human),'ai_topic_ids':sorted(ai)if ai is not None else None,'added_topic_ids':sorted(human-ai)if ai is not None else[],'removed_topic_ids':sorted(ai-human)if ai is not None else[],'human_decision':review['decision'],'ai_decision':draft['decision']if draft else None,'rationale':review['rationale'],'change_reason':review.get('change_reason'),'reviewed_at':review['reviewed_at'],'evaluation_reference_eligible':False})
  except (ValueError,KeyError,TypeError)as error:held.append({'case_id':case,'reviewer_id':reviewer,'hold_reason':str(error)})
 # Conflicting submissions from the same reviewer are all held, never first-write-wins.
 duplicates={key for key in seen if sum((r.get('case_id'),r.get('reviewer_id'))==key for r in reviews)>1}
 kept=[]
 for r in result:
  if(r['case_id'],r['reviewer_id'])in duplicates:held.append({'case_id':r['case_id'],'reviewer_id':r['reviewer_id'],'hold_reason':'duplicate reviewer/case; explicit revision resolution required'})
  else:kept.append(r)
 return {'schema':'cheongju-topic-review-comparison/1','reviews':kept,'held':held,'accepted_reviews':len(kept),'agreements':sum(r['comparison']=='agreement'for r in kept),'disagreements':sum(r['comparison']=='disagreement'for r in kept),'accuracy_computed':False,'gold_reference_created':False,'interest_scores_computed':0,'official_site_requests':0}
def load_release(folder,manifest_name,output):
 manifest=json.loads((folder/manifest_name).read_text());meta=manifest['outputs'][output];raw=(folder/meta['file']).read_bytes()
 if sha(raw)!=meta['sha256']or len(raw)!=meta['bytes']:raise ValueError('release hash/size mismatch')
 rows=[json.loads(line)for line in gzip.decompress(raw).splitlines()]
 if len(rows)!=meta['rows']:raise ValueError('release row count mismatch')
 return manifest,rows
def build(root=ROOT,reviews_path=None):
 root=Path(root);folder=root/'exports/topic-review';bookraw=(root/'config/policy_topics_v1.json').read_bytes();book=json.loads(bookraw);book_hash=sha(bookraw)
 manifest,tasks=load_release(folder,'manifest.json','review_tasks');dm,drafts=load_release(folder,'draft_manifest.json','draft_review');_,records=load_release(root/'exports/processing','member_text_inputs_manifest.json','eligible')
 if manifest['codebook_sha256']!=book_hash or dm['codebook_sha256']!=book_hash or dm['source_task_manifest_sha256']!=sha((folder/'manifest.json').read_bytes()):raise ValueError('review snapshot mismatch')
 if len({d['case_id']for d in drafts})!=len(drafts):raise ValueError('duplicate draft cases')
 reviews=[json.loads(line)for line in Path(reviews_path).read_bytes().splitlines()]if reviews_path else[]
 result=compare(reviews,{t['case_id']:t for t in tasks},{r['activity_id']:r for r in records},{d['case_id']:d for d in drafts},book,book_hash)
 result.update(codebook_sha256=book_hash,source_task_manifest_sha256=sha((folder/'manifest.json').read_bytes()),review_input_sha256=sha(Path(reviews_path).read_bytes())if reviews_path else None)
 write_json(root/'reports/topic-review-comparison-latest.json',result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--reviews',type=Path);a=p.parse_args();print(json.dumps(build(a.root,a.reviews),ensure_ascii=False,indent=2))
