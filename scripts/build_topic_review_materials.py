"""Create reproducible topic-review tasks; never infer labels or interest scores."""
from __future__ import annotations
import argparse,collections,gzip,json
from pathlib import Path
from process_meeting_segments import sha,encoded,pack,write_json
ROOT=Path(__file__).resolve().parents[1]
SEED='cheongju-topic-development-20261104-v1'
def balanced(records,n):
 groups=collections.defaultdict(lambda:collections.defaultdict(list))
 for r in records:groups[r['term']][r['person_id']].append(r)
 queues={}
 for term,people in groups.items():
  order=sorted(people,key=lambda pid:sha((SEED+'|'+str(term)+'|'+pid).encode()))
  for pid in order:people[pid].sort(key=lambda r:sha((SEED+'|'+r['activity_id']+'|'+r['member_text_sha256']).encode()))
  q=[]
  while any(people.values()):
   for pid in order:
    if people[pid]:q.append(people[pid].pop(0))
  queues[term]=q
 result=[]
 while len(result)<min(n,len(records)):
  for term in sorted(queues):
   if queues[term]and len(result)<n:result.append(queues[term].pop(0))
 return result

def sample(records,target=40,question_cap=13):
 questions=[r for r in records if r['source_dataset']=='city_questions'];speeches=[r for r in records if r['source_dataset']=='five_minute_speeches'];q=balanced(questions,min(question_cap,target));s=balanced(speeches,target-len(q));chosen=q+s
 if len(chosen)<min(target,len(records)):
  used={r['activity_id']for r in chosen};chosen+=balanced([r for r in records if r['activity_id']not in used],target-len(chosen))
 return chosen

def validate_annotation(a,record,book,book_hash):
 if a.get('activity_id')!=record['activity_id']or a.get('member_text_sha256')!=record['member_text_sha256']or a.get('codebook_sha256')!=book_hash:raise ValueError('annotation source/codebook version mismatch')
 if a.get('status')!='completed'or a.get('review_origin')!='human'or not isinstance(a.get('reviewer_id'),str)or not a['reviewer_id'].strip():raise ValueError('human review not completed')
 allowed={t['id']for t in book['topics']};labels=a.get('topic_ids');decision=a.get('decision')
 if not isinstance(labels,list)or len(labels)!=len(set(labels))or not set(labels)<=allowed:raise ValueError('invalid topic labels')
 if decision not in {'coded','no_policy','ambiguous'}or(decision=='coded')!=bool(labels):raise ValueError('annotation decision/labels mismatch')
 if not isinstance(a.get('rationale'),str)or not a['rationale'].strip():raise ValueError('annotation rationale missing')
 support=set();text=record['member_text']
 for e in a.get('evidence_spans',[]):
  start,end=e.get('start'),e.get('end')
  if e.get('topic_id')not in labels or type(start)is not int or type(end)is not int or not 0<=start<end<=len(text)or e.get('quote')!=text[start:end]:raise ValueError('annotation evidence not exact source text')
  support.add(e['topic_id'])
 if support!=set(labels):raise ValueError('annotation label lacks source evidence')
 return True

def build(root=ROOT,codebook_path=None):
 root=Path(root);src=root/'exports/processing';dest=root/'exports/topic-review';dest.mkdir(parents=True,exist_ok=True);bookraw=(Path(codebook_path)if codebook_path else root/'config/policy_topics_v1.json').read_bytes();book=json.loads(bookraw);book_hash=sha(bookraw)
 if book.get('schema')!='cheongju-policy-topic-codebook/1'or not book.get('version')or not book.get('topics'):raise ValueError('invalid topic codebook')
 topic_ids=[t['id']for t in book['topics']]
 if len(topic_ids)!=len(set(topic_ids))or any(not t.get(k)for t in book['topics']for k in ['definition','include','exclude','positive_example','negative_example']):raise ValueError('incomplete topic definitions')
 rawmf=(src/'member_text_inputs_manifest.json').read_bytes();mf=json.loads(rawmf)
 if mf.get('schema')!='cheongju-member-text-input-release/1':raise ValueError('topic input manifest schema mismatch')
 meta=mf['outputs']['eligible'];raw=(src/meta['file']).read_bytes()
 if sha(raw)!=meta['sha256']or len(raw)!=meta['bytes']:raise ValueError('topic input hash/size mismatch')
 records=[json.loads(l)for l in gzip.decompress(raw).splitlines()]
 if len(records)!=meta['rows']or len({r['activity_id']for r in records})!=len(records):raise ValueError('topic input row/ID mismatch')
 for r in records:
  if r.get('text_input_eligible')is not True or r.get('hold_reasons')or r.get('source_dataset')not in {'five_minute_speeches','city_questions'}or not r.get('person_id')or sha(r['member_text'].encode())!=r['member_text_sha256']or len(r.get('source_content_proofs',[]))!=1:raise ValueError('unverified text entered topic review')
 chosen=sample(records);selected={r['activity_id']for r in chosen};tasks=[];templates=[]
 for r in sorted(records,key=lambda r:r['activity_id']):
  case_id=sha((r['activity_id']+'|'+r['member_text_sha256']+'|'+book_hash).encode())[:24]
  task={k:r[k]for k in ['activity_id','member_text_sha256','person_id','person_name','date','term','source_dataset','activity_url','source_content_proofs']};task.update(case_id=case_id,codebook_version=book['version'],codebook_sha256=book_hash,partition='development_sample'if r['activity_id']in selected else'reserve_unannotated',review_status='unreviewed',topic_ids=None,interest_score_ready=False);tasks.append(task)
  if r['activity_id']in selected:
   templates.append({**task,'member_text':r['member_text'],'reviewer_id':None,'review_origin':None,'status':'unreviewed','decision':None,'evidence_spans':[],'rationale':None})
 outputs={}
 for name,rows in [('review_tasks',tasks),('development_sample',templates)]:
  payload=pack(b''.join(encoded(r)for r in rows));filename=name+'.jsonl.gz';(dest/filename).write_bytes(payload);outputs[name]={'file':filename,'rows':len(rows),'bytes':len(payload),'sha256':sha(payload)}
 counts=collections.Counter((r['term'],r['source_dataset'])for r in chosen)
 summary={'schema':'cheongju-topic-review-preparation/1','status':'PASS','codebook_version':book['version'],'topic_definitions':len(topic_ids),'eligible_source_records':len(records),'development_sample_records':len(chosen),'reserve_unannotated_records':len(records)-len(chosen),'sample_strata':[{'term':t,'source_dataset':d,'records':n}for(t,d),n in sorted(counts.items())],'sampling_seed':SEED,'sample_purpose':'development_not_unbiased_accuracy_estimation','completed_human_reviews':0,'topic_assignments_computed':0,'interest_scores_computed':0,'official_site_requests':0}
 write_json(dest/'manifest.json',{'schema':'cheongju-topic-review-release/1','script_sha256':sha(Path(__file__).read_bytes()),'source_member_text_inputs_manifest_sha256':sha(rawmf),'source_text_sha256':meta['sha256'],'codebook_sha256':book_hash,'codebook_version':book['version'],'outputs':outputs});write_json(root/'reports/topic-review-materials-latest.json',summary);return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(build(a.root),ensure_ascii=False,indent=2))
