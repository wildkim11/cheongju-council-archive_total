"""Compare independently supplied human reviews with AI drafts; never create gold labels."""
from __future__ import annotations
import argparse,collections,gzip,itertools,json
from datetime import datetime
from pathlib import Path
from build_topic_review_materials import validate_annotation
from process_meeting_segments import sha,write_json
ROOT=Path(__file__).resolve().parents[1]
def compare(reviews,tasks,records,drafts,book,book_hash):
 result=[];held=[];seen=set();keys=[]
 for line_number,review in enumerate(reviews,1):
  case=review.get('case_id')if isinstance(review,dict)else None;reviewer=review.get('reviewer_id')if isinstance(review,dict)else None
  try:
   if not isinstance(review,dict)or not isinstance(case,str)or not isinstance(reviewer,str)or not reviewer.strip():raise ValueError('review must be an object with string case/reviewer IDs')
   key=(case,reviewer);keys.append(key)
   if key in seen:raise ValueError('duplicate reviewer/case; explicit revision resolution required')
   seen.add(key);task=tasks.get(case)
   if task is None:raise ValueError('unknown or stale review case')
   if review.get('full_text_read')is not True:raise ValueError('full text review not declared')
   if review.get('review_method')not in {'independent','ai_assisted','peer_assisted'}:raise ValueError('review method missing')
   if review.get('peer_review_seen')is True and review['review_method']=='independent':raise ValueError('peer review exposure cannot be independent')
   if not isinstance(review.get('reviewed_at'),str)or not review['reviewed_at'].strip():raise ValueError('review timestamp missing')
   datetime.fromisoformat(review['reviewed_at'].replace('Z','+00:00'))
   validate_annotation(review,records[task['activity_id']],book,book_hash)
   draft=drafts.get(case);human=set(review['topic_ids']);ai=set(draft['topic_ids'])if draft else None
   changed=ai is not None and(human!=ai or review['decision']!=draft['decision'])
   if changed and not str(review.get('change_reason')or'').strip():raise ValueError('changed coding requires change reason')
   result.append({'case_id':case,'activity_id':task['activity_id'],'member_text_sha256':review['member_text_sha256'],'evidence_spans':review['evidence_spans'],'reviewer_id':reviewer,'review_method':review['review_method'],'peer_review_seen':review.get('peer_review_seen',False),'comparison':'no_ai_draft'if ai is None else'disagreement'if changed else'unresolved'if review['decision']=='ambiguous'else'agreement','human_topic_ids':sorted(human),'ai_topic_ids':sorted(ai)if ai is not None else None,'added_topic_ids':sorted(human-ai)if ai is not None else[],'removed_topic_ids':sorted(ai-human)if ai is not None else[],'human_decision':review['decision'],'ai_decision':draft['decision']if draft else None,'rationale':review['rationale'],'change_reason':review.get('change_reason'),'reviewed_at':review['reviewed_at'],'evaluation_reference_eligible':False})
  except (ValueError,KeyError,TypeError)as error:held.append({'line_number':line_number,'case_id':case if isinstance(case,str)else None,'reviewer_id':reviewer if isinstance(reviewer,str)else None,'hold_reason':str(error)})
 # Conflicting submissions from the same reviewer are all held, never first-write-wins.
 duplicates={key for key,count in collections.Counter(keys).items()if count>1}
 kept=[]
 for r in result:
  if(r['case_id'],r['reviewer_id'])in duplicates:held.append({'case_id':r['case_id'],'reviewer_id':r['reviewer_id'],'hold_reason':'duplicate reviewer/case; explicit revision resolution required'})
  else:kept.append(r)
 summary=reviewer_summary(kept)
 return {'reviewer_comparison':summary,'schema':'cheongju-topic-review-comparison/1','reviews':kept,'held':held,'accepted_reviews':len(kept),'agreements':sum(r['comparison']=='agreement'for r in kept),'disagreements':sum(r['comparison']=='disagreement'for r in kept),'accuracy_computed':False,'gold_reference_created':False,'interest_scores_computed':0,'official_site_requests':0}
def reviewer_summary(reviews):
 bycase=collections.defaultdict(list)
 for r in reviews:bycase[r['case_id']].append(r)
 cases=[];pair_count=0;independent=0;with_ai=0;with_peer=0;disagreements=0;ambiguous=0
 for case,rows in sorted(bycase.items()):
  pairs=[]
  for left,right in itertools.combinations(sorted(rows,key=lambda r:r['reviewer_id']),2):
   a=set(left['human_topic_ids']);b=set(right['human_topic_ids']);decision_diff=left['human_decision']!=right['human_decision'];topic_diff=a!=b
   is_independent=left['review_method']==right['review_method']=='independent';is_ambiguous='ambiguous'in {left['human_decision'],right['human_decision']}
   # Two identical "ambiguous" responses are unresolved, never classification agreement.
   outcome='disagreement'if decision_diff or topic_diff else'unresolved'if is_ambiguous else'agreement'
   pairs.append({'reviewer_a':left['reviewer_id'],'reviewer_b':right['reviewer_id'],'method_group':'self_reported_independent'if is_independent else'includes_assistance','outcome':outcome,'decision_differs':decision_diff,'topic_ids_only_a':sorted(a-b),'topic_ids_only_b':sorted(b-a)})
   pair_count+=1;independent+=is_independent;with_ai+=any(r['review_method']=='ai_assisted'for r in [left,right]);with_peer+=any(r['review_method']=='peer_assisted'or r.get('peer_review_seen')is True for r in [left,right]);disagreements+=outcome=='disagreement';ambiguous+=is_ambiguous
  cases.append({'case_id':case,'activity_id':rows[0]['activity_id'],'reviewer_count':len(rows),'has_multiple_reviewers':len(rows)>1,'requires_resolution':any(p['outcome']!='agreement'for p in pairs)or any(r['human_decision']=='ambiguous'for r in rows),'pairs':pairs})
 return {'status':'no_reviews'if not reviews else'insufficient_overlap'if not pair_count else'descriptive_comparison_only','cases':cases,'cases_with_multiple_reviewers':sum(c['has_multiple_reviewers']for c in cases),'reviewer_pair_comparisons':pair_count,'self_reported_independent_pairs':independent,'pairs_including_ai_assistance':with_ai,'pairs_including_peer_assistance':with_peer,'disagreeing_pairs':disagreements,'pairs_including_ambiguous':ambiguous,'agreement_rate':None,'reliability_coefficient':None,'gold_reference_created':False,'majority_vote_applied':False,'note':'Pairs share reviewers/cases and are not independent observations. No accuracy, reliability estimate, consensus or final labels are inferred.'}

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
 reviews=[]
 if reviews_path:
  for line in Path(reviews_path).read_text().splitlines():
   try:reviews.append(json.loads(line))
   except json.JSONDecodeError:reviews.append(None)
 result=compare(reviews,{t['case_id']:t for t in tasks},{r['activity_id']:r for r in records},{d['case_id']:d for d in drafts},book,book_hash)
 result.update(codebook_sha256=book_hash,source_task_manifest_sha256=sha((folder/'manifest.json').read_bytes()),review_input_sha256=sha(Path(reviews_path).read_bytes())if reviews_path else None)
 write_json(root/'reports/topic-review-comparison-latest.json',result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--reviews',type=Path);a=p.parse_args();print(json.dumps(build(a.root,a.reviews),ensure_ascii=False,indent=2))
