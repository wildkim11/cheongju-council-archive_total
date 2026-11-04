import copy,datetime as dt,sys,unittest,json,tempfile,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collection_runner_recovery as r,collection_policy as p
class StartupRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.now=dt.datetime(2026,11,4,5,tzinfo=dt.timezone.utc);self.failure={'id':1,'status':'completed','conclusion':'failure','created_at':'2026-11-03T21:35:00Z','updated_at':'2026-11-03T22:43:00Z','jobs':[{'name':'collect','status':'completed','conclusion':'cancelled','steps':[]}]}
 def decide(self,state=None,recovery=None,failure=None):return r.decide(state or{},recovery or{},self.failure if failure is None else failure,self.now)
 def test_startup_failure_recovers_only_uncheckpointed(self):
  d=self.decide({'families':{'minutes':{'last_success_at':'2026-11-04T00:00:00Z'}}});self.assertEqual(d['mode'],'startup_retry');self.assertNotIn('minutes',d['targets']);self.assertEqual(len(d['targets']),6)
 def test_source_failures_keep_own_retry_policy(self):
  d=self.decide({'families':{'bills':{'consecutive_failures':1,'next_retry_at':'2026-11-05T00:00:00Z'}}});self.assertNotIn('bills',d['targets'])
 def test_reserve_before_runner_start_and_backoff(self):
  d=self.decide();self.assertEqual(d['state']['retry_attempts_today'],1);again=self.decide(recovery=d['state']);self.assertEqual(again['mode'],'skip');self.assertIn('backoff',again['reason'])
 def test_three_startup_retries_max_per_korean_day(self):
  old={'schema':r.SCHEMA,'attempt_day':p.day(self.now),'retry_attempts_today':3};self.assertIn('budget',self.decide(recovery=old)['reason'])
 def test_budget_resets_on_korean_day(self):
  old={'schema':r.SCHEMA,'attempt_day':'2026-11-03','retry_attempts_today':3};self.assertEqual(self.decide(recovery=old)['state']['retry_attempts_today'],1)
 def test_step_started_failure_not_misclassified(self):
  f=copy.deepcopy(self.failure);f['jobs'][0]['steps']=[{'name':'Set up job'}];self.assertEqual(self.decide(failure=f)['mode'],'skip')
 def test_manual_cancellation_not_retried(self):
  f=copy.deepcopy(self.failure);f['conclusion']='cancelled';self.assertEqual(self.decide(failure=f)['mode'],'skip')
 def test_stale_failure_not_retried(self):
  f=copy.deepcopy(self.failure);f['created_at']='2026-11-01T21:00:00Z';f['updated_at']='2026-11-01T22:00:00Z';self.assertEqual(self.decide(failure=f)['mode'],'skip')
 def test_gate_success_has_no_official_target(self):self.assertEqual(self.decide(failure={})['targets'],[])
 def test_all_checkpointed_no_recovery(self):
  state={'families':{n:{'last_success_at':'2026-11-04T00:00:00Z'}for n in p.FAMILIES}};self.assertEqual(self.decide(state)['mode'],'skip')
 def test_pending_reservation_skips_already_finished_family(self):
  d=self.decide();state={'families':{'minutes':{'last_success_at':'2026-11-04T05:01:00Z'},'bills':{'consecutive_failures':1}}};self.assertNotIn('minutes',r.pending_targets(d['state'],state));self.assertNotIn('bills',r.pending_targets(d['state'],state))
 def test_bad_reservation_fails_closed(self):
  with self.assertRaises(ValueError):r.pending_targets({'schema':r.SCHEMA,'pending_targets':['unexpected']})
 def test_policy_cli_emits_startup_plan_and_reservation(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);now=dt.datetime.now(dt.timezone.utc);f=copy.deepcopy(self.failure);f.update(created_at=(now-dt.timedelta(hours=2)).isoformat(),updated_at=(now-dt.timedelta(hours=1)).isoformat())
   for name,data in [('state.json',{}),('recovery.json',{'schema':r.SCHEMA}),('failure.json',f)]:(root/name).write_text(json.dumps(data))
   result=subprocess.run([sys.executable,str(Path(p.__file__)),'plan','--state',str(root/'state.json'),'--event','schedule','--schedule',p.RETRY_CRON,'--runner-failure',str(root/'failure.json'),'--runner-recovery',str(root/'recovery.json'),'--runner-decision',str(root/'decision.json')],capture_output=True,text=True,check=True);self.assertIn('mode=startup_retry',result.stdout);self.assertEqual(json.loads((root/'decision.json').read_text())['retry_attempts_today'],1)
 def test_configuration_push_never_forces_full_collection(self):self.assertEqual(p.plan('push','','all',{},self.now),'skip')
if __name__=='__main__':unittest.main()
