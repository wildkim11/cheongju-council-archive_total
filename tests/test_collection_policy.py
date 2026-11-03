import datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collection_policy as p
class SchedulePolicyTests(unittest.TestCase):
 def setUp(self):self.now=dt.datetime(2026,11,3,16,0,tzinfo=dt.timezone.utc)
 def state(self,**kw):return {'families':{'minutes':{'consecutive_failures':1,'next_retry_at':'2026-11-03T15:00:00+00:00',**kw},'bills':{'consecutive_failures':0,'last_success_at':'2026-11-03T15:30:00+00:00'}}}
 def test_daily_runs_all_not_one_seventh(self):self.assertEqual(p.plan('schedule',p.DAILY_CRON,'',{},self.now),'all')
 def test_healthy_hourly_check_skips_official_collection(self):self.assertEqual(p.plan('schedule',p.RETRY_CRON,'',{},self.now),'skip')
 def test_only_failed_family_selected(self):self.assertEqual(p.due_families(self.state(),self.now),['minutes'])
 def test_not_before_backoff(self):self.assertEqual(p.due_families(self.state(next_retry_at='2026-11-04T00:00:00+00:00'),self.now),[])
 def test_three_extra_attempt_budget(self):self.assertEqual(p.due_families(self.state(retry_attempts_day='2026-11-04',retry_attempts_today=3),self.now),[])
 def test_budget_resets_at_korean_midnight(self):self.assertEqual(p.due_families(self.state(retry_attempts_day='2026-11-03',retry_attempts_today=3),self.now),['minutes'])
 def test_failed_document_queue_eligible_even_after_snapshot_success(self):self.assertEqual(p.due_families({'families':{'attachments':{'failed_documents':2,'pending_attachment_retry_at':'2026-11-03T15:00:00+00:00'}}},self.now),['attachments'])
if __name__=='__main__':unittest.main()
