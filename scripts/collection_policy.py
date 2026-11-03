"""One daily full cycle; retries target due failures with a Korean-day budget."""
from __future__ import annotations
import argparse,datetime as dt,json,os
from pathlib import Path
FAMILIES=('minutes','bills','activities','people','groups','media','attachments')
KST=dt.timezone(dt.timedelta(hours=9));MAX_RETRIES=3
DAILY_CRON='0 21 * * *';RETRY_CRON='17 * * * *'
def day(now):return now.astimezone(KST).date().isoformat()
def retry_budget(slot,now):return slot.get('retry_attempts_day')!=day(now) or int(slot.get('retry_attempts_today',0))<MAX_RETRIES
def failed_due(slot,now):
    if not retry_budget(slot,now):return False
    times=[]
    if slot.get('consecutive_failures',0)>0:times.append(slot.get('next_retry_at'))
    if slot.get('failed_documents',0)>0:times.append(slot.get('pending_attachment_retry_at'))
    for stamp in times:
        if stamp and dt.datetime.fromisoformat(stamp)<=now:return True
    return False
def due_families(state,now):return [f for f in FAMILIES if failed_due(state.get('families',{}).get(f,{}),now)]
def plan(event,schedule,requested,state,now):
    if event=='schedule':
        if schedule==DAILY_CRON:return 'all'
        if schedule==RETRY_CRON:return 'retry' if due_families(state,now) else 'skip'
        raise ValueError('unknown schedule')
    return requested or 'all'
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['due','plan']);p.add_argument('--state',type=Path,required=True);p.add_argument('--event',default='workflow_dispatch');p.add_argument('--schedule',default='');p.add_argument('--requested',default='all');a=p.parse_args();state=json.loads(a.state.read_text()) if a.state.exists() else {};now=dt.datetime.now(dt.timezone.utc)
 if a.action=='due':print(' '.join(due_families(state,now)));return
 mode=plan(a.event,a.schedule,a.requested,state,now)
 if mode not in ('all','retry','skip','bootstrap','auto')+FAMILIES:raise ValueError('unknown collection mode')
 output=f'run={str(mode!="skip").lower()}\nmode={mode}\n'
 if os.getenv('GITHUB_OUTPUT'):
  with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write(output)
 print(output,end='')
if __name__=='__main__':main()
