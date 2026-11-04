import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_member_activity_counts as b
class CountsTests(unittest.TestCase):
 def row(self,**changes):return {'activity_id':'bill:4:1:p:representative','person_id':'p','person_name':'가나다','term':4,'count_council_scope':'scope','kind':'bill','role':'representative','date':'2026-01-01','title':'의안','official_url':'https://councilrec.cheongju.go.kr/x','source_dataset':'bill_proposers_member_only','source_row_1based':1,'analysis_gate':{'base_count_eligible':True},**changes}
 def test_roles_and_unique_bills(self):
  r=self.row();x=self.row(activity_id='bill:4:2:p:co_proposer',role='co_proposer');v=b.summarize([r,x]);self.assertEqual((v['bill_events'],v['representative_bills'],v['co_proposed_bills']),(2,1,1))
 def test_duplicate_event_rejected(self):
  with self.assertRaises(ValueError):b.summarize([self.row(),self.row(role='co_proposer')])
 def test_held_cannot_enter_counts(self):
  with self.assertRaises(ValueError):b.summarize([self.row(analysis_gate={'base_count_eligible':False})])
 def test_missing_name_identity_rejected(self):
  with self.assertRaises(ValueError):b.aggregate([self.row()],[],{'p':{'name':'다른사람'}})
 def test_unassigned_held_never_assigned_to_member(self):
  p,n=b.aggregate([], [self.row(person_id=None,analysis_gate={'base_count_eligible':False})],{});self.assertEqual((p,n),([],1))
 def test_held_and_eligible_duplicate_rejected(self):
  with self.assertRaises(ValueError):b.aggregate([self.row()],[self.row(analysis_gate={'base_count_eligible':False})],{'p':{'name':'가나다'}})
 def test_no_merge_across_terms(self):
  a=self.row();c=self.row(activity_id='bill:3:2:p:representative',term=3);p,_=b.aggregate([a,c],[],{'p':{'name':'가나다'}});self.assertEqual(len(p),2)
 def test_nonbill_count_and_evidence_url_kept(self):
  r=self.row(activity_id='five:1:speaker',kind='five_minute_speech',role='speaker',source_dataset='five_minute_speeches');p,_=b.aggregate([r],[],{'p':{'name':'가나다'}});self.assertEqual(p[0]['counts']['five_minute_speech'],1);self.assertEqual(p[0]['eligible'][0]['official_url'],r['official_url'])
