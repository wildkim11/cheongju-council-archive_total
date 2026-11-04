"""Attach archived dated context to activity roles without guessing missing periods."""
from __future__ import annotations
import argparse,collections,datetime as dt,gzip,json,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from process_meeting_segments import encoded,pack,load_export,write_json,sha
ROOT=Path(__file__).resolve().parents[1]
HISTORIES=('tenures','committee_memberships','party_memberships','district_memberships')
SOURCES=('bill_proposers_member_only','five_minute_speeches','city_questions','written_questions')
def date(value):
 try:return dt.date.fromisoformat(value) if value else None
 except (ValueError,TypeError):return None

def official(url):
 try:
  u=urlsplit(url or '');return u.scheme=='https' and u.hostname in {'council.cheongju.go.kr','councilrec.cheongju.go.kr'} and not u.username and not u.password
 except ValueError:return False

def join_history(rows,dataset,person_id,scope,term,when):
 observed=date(when)
 if not person_id or not scope or term is None or not observed:return {'status':'missing_identity_term_or_date','facts':[],'held_refs':[],'outside_refs':[]}
 candidates=[(i,r) for i,r in enumerate(rows,1) if r.get('person_id')==person_id and r.get('council_scope')==scope and r.get('term')==term]
 facts=[];held=[];outside_refs=[]
 for i,r in candidates:
  ref=dataset+':'+str(i);start,end=date(r.get('start_date')),date(r.get('end_date'))
  valid_label=dataset=='tenures' or bool(r.get('party') if dataset=='party_memberships' else r.get('label'))
  if not official(r.get('source_url')) or r.get('displayed_period_conflict') or r.get('period_precision') not in {'exact_date','start_exact_end_unknown','end_exact_start_unknown'} or not valid_label:held.append(ref);continue
  if start and end and start>end:held.append(ref);continue
  if start and observed<start or end and observed>end:
   outside_refs.append({'row_ref':ref,'start_date':r.get('start_date'),'end_date':r.get('end_date'),'source_url':r.get('source_url'),'record_sha256':sha(encoded(r))});continue
  exact=start and end and r.get('period_precision')=='exact_date' and not r.get('displayed_period_conflict') and official(r.get('source_url'))
  if not exact:held.append(ref);continue
  facts.append({'row_ref':ref,'record_sha256':sha(encoded(r)),'source_url':r['source_url'],'start_date':r['start_date'],'end_date':r['end_date'],**{k:r[k] for k in ('party','label','role','committee_code','membership_type') if k in r}})
 values={(f.get('party') if dataset=='party_memberships' else f.get('label')) for f in facts}
 conflict=dataset in {'party_memberships','district_memberships'} and len(values)>1
 status='conflicting_facts' if conflict else 'partial_interval_evidence' if facts and held else 'archived_explicit_interval' if facts else 'incomplete_interval' if held else 'outside_recorded_intervals' if candidates else 'no_history_records'
 return {'status':status,'facts':facts,'held_refs':held,'outside_refs':outside_refs}

def build(root=ROOT):
 root=Path(root);out=root/'exports/processing';mf=json.loads((root/'exports/analyzer/manifest.json').read_text());names=('people',)+HISTORIES+SOURCES
 data={name:load_export(root,name,mf) for name in names};people={r['person_id']:r for r in data['people']}
 if len(people)!=len(data['people']):raise ValueError('duplicate person ID')
 processing=json.loads((out/'manifest.json').read_text());raw=(out/'activity_roles.jsonl.gz').read_bytes()
 if sha(raw)!=processing['activity_roles']['sha256']:raise ValueError('activity role hash mismatch')
 roles=[json.loads(line) for line in gzip.decompress(raw).splitlines()]
 if len(roles)!=processing['activity_roles']['rows']:raise ValueError('activity role count mismatch')
 result=[];review=[];seen=set();counts={name:collections.Counter() for name in HISTORIES};ready=0
 for activity in roles:
  aid=activity['activity_id']
  if aid in seen:raise ValueError('duplicate activity ID')
  seen.add(aid);name=activity['source_dataset'];n=activity['source_row_1based']
  if name not in SOURCES or not isinstance(n,int) or not 1<=n<=len(data[name]):raise ValueError('activity source row missing')
  source=data[name][n-1];pid=activity.get('person_id');scope=source.get('council_scope');term=activity.get('term');when=activity.get('date')
  if pid and (pid not in people or people[pid]['name']!=activity['person_name']):raise ValueError('activity person/name mismatch')
  context={name:join_history(data[name],name,pid,scope,term,when) for name in HISTORIES}
  for name,c in context.items():counts[name][c['status']]+=1
  group_ready=all(context[name]['status']=='archived_explicit_interval' for name in ('tenures','party_memberships','district_memberships'))
  conflict=context['tenures']['status']=='outside_recorded_intervals'
  if conflict:review.append({'activity_id':aid,'person_id':pid,'person_name':activity['person_name'],'date':when,'term':term,'activity_source_ref':activity['source_dataset']+':'+str(n),'official_url':activity['official_url'],'tenure_evidence':context['tenures']['outside_refs'],'status':'archived_date_conflict_review_required'})
  opportunity_ready=group_ready and context['committee_memberships']['status']=='archived_explicit_interval';ready+=group_ready
  result.append({'activity_id':aid,'person_id':pid,'date':when,'term':term,'council_scope':scope,'identity_status':activity['identity_status'],'temporal_conflict_review_required':conflict,'activity_source_ref':activity['source_dataset']+':'+str(n),'activity_official_url':activity['official_url'],'context':context,'group_comparison_ready':group_ready,'committee_opportunity_ready':opportunity_ready})
 encoded_rows=b''.join(encoded(x) for x in result);compressed=pack(encoded_rows)
 # Keep an independent input/output contract; no scores or source identity changes.
 manifest={'schema':'cheongju-activity-temporal-context/1','script_sha256':sha(Path(__file__).read_bytes()),'source_activity_roles_sha256':sha(raw),'analyzer_inputs':{name:mf['datasets'][name] for name in names},'output':{'file':'activity_temporal_context.jsonl.gz','rows':len(result),'sha256':sha(compressed),'bytes':len(compressed)}}
 summary={'status':'PASS','scope':'archived_explicit_dates_only_not_full_history_verification','activity_rows':len(result),'temporal_conflict_rows':len(review),'review_cases':review,'group_comparison_ready':ready,'committee_opportunity_ready':sum(r['committee_opportunity_ready'] for r in result),'contexts':{k:dict(v) for k,v in counts.items()},'source_rows':{n:len(data[n]) for n in HISTORIES},'official_site_requests':0}
 (out/'activity_temporal_context.jsonl.gz').write_bytes(compressed);write_json(out/'temporal_context_manifest.json',manifest);write_json(root/'reports/temporal-context-latest.json',summary)
 return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(build(a.root),ensure_ascii=False,indent=2))
