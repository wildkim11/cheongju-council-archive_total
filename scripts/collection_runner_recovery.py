"""Bounded recovery of failed workflows whose macOS collection never started or stopped after partial checkpoints.

This module only reads supplied GitHub metadata. It never requests official sites.
"""
from __future__ import annotations
import argparse,copy,datetime as dt,json
from pathlib import Path
from collection_policy import FAMILIES,MAX_RETRIES,day
SCHEMA='cheongju-runner-recovery/1'
def stamp(value):
 parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
 if parsed.tzinfo is None:raise ValueError('timezone required')
 return parsed

def decide(state,recovery,failure,now):
 old=copy.deepcopy(recovery or {'schema':SCHEMA})
 if old.get('schema')!=SCHEMA:raise ValueError('unknown runner recovery schema')
 result={'mode':'skip','reason':'no eligible collection startup failure','state':old,'targets':[]}
 if not failure:return result
 if failure.get('status')!='completed'or failure.get('conclusion')!='failure':return result
 collect=[j for j in failure.get('jobs',[])if j.get('name')=='collect']
 if len(collect)!=1 or collect[0].get('status')!='completed'or collect[0].get('conclusion')not in {'cancelled','failure','timed_out'}:return result
 steps=collect[0].get('steps');startup=steps==[]
 interrupted=isinstance(steps,list)and any(s.get('name')=='Collect into isolated candidate and publish only after validation'and s.get('conclusion')in {'failure','cancelled','timed_out'}for s in steps)
 if not startup and not interrupted:return result
 start=stamp(failure['created_at']);end=stamp(failure['updated_at'])
 if end<start or end>now or now-end>dt.timedelta(hours=24):return result
 if not startup and not any(slot.get('last_success_at')and stamp(slot['last_success_at'])>=start for slot in state.get('families',{}).values()):return result
 # Only source families still missing their checkpoint for this failed cycle.
 # Controller-recorded source failures keep their own backoff and retry budget.
 targets=[]
 for name in FAMILIES:
  slot=state.get('families',{}).get(name,{})
  if slot.get('consecutive_failures',0)>0:continue
  if slot.get('last_success_at')and stamp(slot['last_success_at'])>=start:continue
  if slot.get('next_retry_at')and stamp(slot['next_retry_at'])>now:continue
  targets.append(name)
 if not targets:result['reason']='failed cycle already checkpointed or handled by source retry';return result
 count=old.get('retry_attempts_today',0)if old.get('attempt_day')==day(now)else 0
 if type(count)is not int or not 0<=count<=MAX_RETRIES:raise ValueError('invalid runner retry budget')
 if count>=MAX_RETRIES:result['reason']='startup retry daily budget exhausted';return result
 if old.get('next_retry_at')and stamp(old['next_retry_at'])>now:result['reason']='startup retry backoff';return result
 reservation={'source_run_id':failure['id'],'source_run_attempt':failure.get('run_attempt',1),'failed_cycle_started_at':start.isoformat(),'reserved_at':now.isoformat(),'targets':targets,'recovery_kind':'not_started'if startup else'partial_cycle_interrupted'}
 old.update(schema=SCHEMA,attempt_day=day(now),retry_attempts_today=count+1,next_retry_at=(now+dt.timedelta(hours=2**count)).isoformat(),pending_targets=targets,last_reserved_at=now.isoformat(),reservations=(old.get('reservations',[])+[reservation])[-20:])
 result.update(mode='startup_retry',reason='retry only uncheckpointed families after eligible collection interruption',state=old,targets=targets)
 return result

def pending_targets(recovery,state=None):
 targets=recovery.get('pending_targets')
 if recovery.get('schema')!=SCHEMA or not isinstance(targets,list)or not targets or any(not isinstance(t,str)or t not in FAMILIES for t in targets)or len(set(targets))!=len(targets)or not recovery.get('last_reserved_at'):raise ValueError('missing or invalid startup retry reservation')
 if state is not None:
  reserved=stamp(recovery['last_reserved_at']);targets=[t for t in targets if not state.get('families',{}).get(t,{}).get('consecutive_failures',0) and(not state.get('families',{}).get(t,{}).get('last_success_at')or stamp(state['families'][t]['last_success_at'])<reserved)]
 return targets
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['targets']);p.add_argument('--recovery',type=Path,required=True);p.add_argument('--state',type=Path);a=p.parse_args();print(' '.join(pending_targets(json.loads(a.recovery.read_text()),json.loads(a.state.read_text())if a.state and a.state.exists()else {})))
