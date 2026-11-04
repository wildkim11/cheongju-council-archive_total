"""Partition analysis inputs while retaining every source row and hold reason."""
from __future__ import annotations
import argparse,collections,datetime as dt,gzip,json
from pathlib import Path
from process_meeting_segments import sha,encoded,pack,write_json
ROOT=Path(__file__).resolve().parents[1]
def classify(role,context):
 for k in ('activity_id','person_id','date','term'):
  if role.get(k)!=context.get(k):raise ValueError('activity/context mismatch: '+k)
 for k in ('temporal_conflict_review_required','group_comparison_ready','committee_opportunity_ready'):
  if type(context.get(k))is not bool:raise ValueError('missing or invalid context flag: '+k)
 c=context['context'];group_supported=all(c[k]['status']=='archived_explicit_interval' for k in ('tenures','party_memberships','district_memberships'))
 if context['group_comparison_ready'] and not group_supported:raise ValueError('group readiness contradicts dated evidence')
 if context['committee_opportunity_ready'] and (not context['group_comparison_ready'] or c['committee_memberships']['status']!='archived_explicit_interval'):raise ValueError('committee readiness contradicts dated evidence')
 reasons=[]
 if not role.get('person_id'):reasons.append('unresolved_person_id')
 if role.get('person_id') and role.get('identity_status') not in {'archive_exact_term_link','resolved_explicit_tenure','resolved_cross_source_exact_body','resolved_source_meeting_term','resolved_cross_source_question_answer'}:reasons.append('unrecognized_identity_basis')
 if not context.get('council_scope') or type(role.get('term'))is not int or (isinstance(role.get('term'),int) and role['term']<=0):reasons.append('missing_council_scope_or_term')
 try:dt.date.fromisoformat(role.get('date'))
 except (TypeError,ValueError):reasons.append('missing_or_invalid_activity_date')
 if context['temporal_conflict_review_required'] or c['tenures']['status']=='outside_recorded_intervals':reasons.append('outside_recorded_tenure')
 if role.get('identity_status') in {'identity_evidence_conflict','ambiguous_dated_tenure'}:reasons.append('conflicting_identity_evidence')
 return sorted(set(reasons))
def build(root=ROOT):
 root=Path(root);out=root/'exports/processing';pm=json.loads((out/'manifest.json').read_text());tm=json.loads((out/'temporal_context_manifest.json').read_text());raw=(out/'activity_roles.jsonl.gz').read_bytes();ctxraw=(out/'activity_temporal_context.jsonl.gz').read_bytes()
 if sha(raw)!=pm['activity_roles']['sha256'] or sha(raw)!=tm['source_activity_roles_sha256'] or sha(ctxraw)!=tm['output']['sha256']:raise ValueError('analysis gate input hash mismatch')
 roles=[json.loads(l)for l in gzip.decompress(raw).splitlines()];contexts=[json.loads(l)for l in gzip.decompress(ctxraw).splitlines()]
 if len(roles)!=pm['activity_roles']['rows'] or len(contexts)!=tm['output']['rows']:raise ValueError('analysis gate input row mismatch')
 by={c['activity_id']:c for c in contexts}
 if len(by)!=len(contexts) or set(by)!={r['activity_id']for r in roles} or len({r['activity_id']for r in roles})!=len(roles):raise ValueError('analysis gate activity IDs mismatch')
 eligible=[];held=[];counts=collections.Counter();kind_counts={};events={}
 for r in roles:
  c=by[r['activity_id']];reasons=classify(r,c);entry={**r,'analysis_gate':{'base_count_eligible':not reasons,'hold_reasons':reasons,'temporal_context_ref':r['activity_id'],'historical_group_eligible':not reasons and c['group_comparison_ready'],'committee_adjustment_eligible':not reasons and c['committee_opportunity_ready']}}
  (held if reasons else eligible).append(entry);counts.update(reasons);bucket=kind_counts.setdefault(r['kind'],{'source_rows':0,'eligible_rows':0,'held_rows':0});bucket['source_rows']+=1;bucket['held_rows' if reasons else 'eligible_rows']+=1
  if r['kind']=='bill':
   # A held participant makes the event's roster incomplete for network consumers.
   key=r['activity_id'].split(':');event=events.setdefault(key[1]+':'+key[2],{'source_participant_rows':0,'eligible_participant_rows':0,'held_activity_ids':[]});event['source_participant_rows']+=1
   if reasons:event['held_activity_ids'].append(r['activity_id'])
   else:event['eligible_participant_rows']+=1
 outputs={}
 for label,rows in [('eligible',eligible),('held',held)]:
  rawout=pack(b''.join(encoded(x)for x in rows));name=label+'_activity_roles.jsonl.gz';(out/name).write_bytes(rawout);outputs[label]={'file':name,'rows':len(rows),'sha256':sha(rawout),'bytes':len(rawout)}
 summary={'status':'PASS','scope':'source_attributed_counts_not_historical_group_or_interest_scores','source_rows':len(roles),'eligible_rows':len(eligible),'held_rows':len(held),'hold_reasons':dict(counts),'kinds':kind_counts,'historical_group_rows':sum(r['analysis_gate']['historical_group_eligible']for r in eligible),'committee_adjustment_rows':sum(r['analysis_gate']['committee_adjustment_eligible']for r in eligible),'incomplete_bill_events':{k:v for k,v in events.items()if v['held_activity_ids']},'official_site_requests':0}
 write_json(out/'analysis_activity_gate_manifest.json',{'schema':'cheongju-analysis-activity-gate/1','script_sha256':sha(Path(__file__).read_bytes()),'input_activity_roles_sha256':sha(raw),'input_temporal_context_sha256':sha(ctxraw),'outputs':outputs});write_json(root/'reports/analysis-activity-gate-latest.json',summary);return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(build(a.root),ensure_ascii=False,indent=2))
