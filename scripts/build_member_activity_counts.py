"""Source-attributed member counts with complete row-level evidence; no scores."""
import argparse,collections,gzip,json
from pathlib import Path
from process_meeting_segments import sha,encoded,pack,write_json
ROOT=Path(__file__).resolve().parents[1]
KINDS={'bill','five_minute_speech','city_question','written_question'}
def event_key(r):
 if r['kind']=='bill':
  parts=r['activity_id'].split(':')
  if parts[0]!='bill' or parts[1]!=str(r['term']):raise ValueError('bill event identity mismatch')
  return 'bill:'+parts[1]+':'+parts[2]
 return r['source_dataset']+':'+str(r['source_row_1based'])
def summarize(rows):
 bills={};counts=collections.Counter();seen=set()
 for r in rows:
  if r['kind']not in KINDS or not r['analysis_gate']['base_count_eligible']:raise ValueError('unsupported or held row entered counts')
  key=event_key(r)
  if key in seen:raise ValueError('duplicate member event or conflicting bill roles')
  seen.add(key);counts[r['kind']]+=1
  if r['kind']=='bill':
   if r['role']not in {'representative','co_proposer'}:raise ValueError('unsupported bill role')
   bills[key]=r['role']
  elif r['role']!='speaker':raise ValueError('unsupported activity role')
 return {'participation_rows':len(rows),'bill_events':len(bills),'representative_bills':sum(v=='representative'for v in bills.values()),'co_proposed_bills':sum(v=='co_proposer'for v in bills.values()),**{k:counts[k]for k in sorted(KINDS)if k!='bill'}}
def aggregate(eligible,held,people):
 profiles={};ids=set();unassigned=0
 for allowed,rows in [(True,eligible),(False,held)]:
  for r in rows:
   if r['activity_id']in ids:raise ValueError('duplicate activity input')
   ids.add(r['activity_id']);gate=r['analysis_gate']
   if gate['base_count_eligible']is not allowed:raise ValueError('gate partition mismatch')
   pid=r.get('person_id')
   if not pid:
    if allowed:raise ValueError('unresolved person in counts')
    unassigned+=1;continue
   if pid not in people or people[pid]['name']!=r['person_name']:raise ValueError('person name mismatch')
   # Scope is retained from the context evidence contract, never inferred by name.
   scope=r.get('count_council_scope');
   if not scope:raise ValueError('missing count scope')
   key=scope+'|'+str(r['term'])+'|'+pid;p=profiles.setdefault(key,{'key':key,'person_id':pid,'name':r['person_name'],'term':r['term'],'council_scope':scope,'eligible':[],'held':[]})
   p['eligible' if allowed else 'held'].append({k:r[k]for k in ['activity_id','date','kind','role','title','official_url','source_dataset','source_row_1based','term','analysis_gate']})
 for p in profiles.values():
  p['counts']=summarize(p['eligible']);p['held_rows']=len(p['held']);p['date_min']=min((r['date']for r in p['eligible']),default=None);p['date_max']=max((r['date']for r in p['eligible']),default=None)
 return sorted(profiles.values(),key=lambda p:(p['council_scope'],p['term'],p['name'],p['person_id'])),unassigned

def build(root=ROOT):
 root=Path(root);out=root/'exports/processing';gate=json.loads((out/'analysis_activity_gate_manifest.json').read_text());tm=json.loads((out/'temporal_context_manifest.json').read_text());ctxraw=(out/'activity_temporal_context.jsonl.gz').read_bytes()
 if sha(ctxraw)!=gate['input_temporal_context_sha256']or sha(ctxraw)!=tm['output']['sha256']:raise ValueError('count context hash mismatch')
 scopes={r['activity_id']:r['council_scope']for r in map(json.loads,gzip.decompress(ctxraw).splitlines())};rows={}
 for label,meta in gate['outputs'].items():
  raw=(out/meta['file']).read_bytes()
  if sha(raw)!=meta['sha256']:raise ValueError('count partition hash mismatch')
  rows[label]=[json.loads(l)for l in gzip.decompress(raw).splitlines()]
  if len(rows[label])!=meta['rows']:raise ValueError('count partition row mismatch')
  for r in rows[label]:r['count_council_scope']=scopes[r['activity_id']]
 from process_meeting_segments import load_export
 mf=json.loads((root/'exports/analyzer/manifest.json').read_text());people_rows=load_export(root,'people',mf);people={p['person_id']:p for p in people_rows}
 if len(people)!=len(people_rows):raise ValueError('duplicate person IDs')
 profiles,unassigned=aggregate(rows['eligible'],rows['held'],people)
 document={'schema':'cheongju-member-activity-counts/1','scope':'source_attributed_activity_rows_not_effectiveness_or_interest_scores','source_rows':sum(len(v)for v in rows.values()),'eligible_rows':len(rows['eligible']),'held_rows':len(rows['held']),'unassigned_held_rows':unassigned,'profiles':profiles}
 raw=pack(encoded(document));(out/'member_activity_counts.json.gz').write_bytes(raw);write_json(out/'member_activity_counts_manifest.json',{'schema':'cheongju-member-activity-counts-release/1','script_sha256':sha(Path(__file__).read_bytes()),'gate_manifest_sha256':sha((out/'analysis_activity_gate_manifest.json').read_bytes()),'people_sha256':mf['datasets']['people']['sha256'],'output':{'file':'member_activity_counts.json.gz','bytes':len(raw),'sha256':sha(raw),'profiles':len(profiles)}})
 summary={'status':'PASS','profile_ids_not_unique_humans':len(profiles),'source_rows':document['source_rows'],'eligible_rows':document['eligible_rows'],'held_rows':document['held_rows'],'unassigned_held_rows':unassigned,'unique_eligible_bill_events':len({r['count_council_scope']+'|'+event_key(r)for r in rows['eligible']if r['kind']=='bill'}),'eligible_bill_participation_rows':sum(p['counts']['bill_events']for p in profiles),'official_site_requests':0};write_json(root/'reports/member-activity-counts-latest.json',summary);return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(build(a.root),ensure_ascii=False,indent=2))
