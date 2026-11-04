import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_analysis_activity_gate as g
class AnalysisGateTests(unittest.TestCase):
 def fixture(self):
  r={'activity_id':'a','person_id':'p','date':'2026-01-01','term':4,'identity_status':'archive_exact_term_link'};c={**r,'council_scope':'cheongju_integrated','temporal_conflict_review_required':False,'group_comparison_ready':False,'committee_opportunity_ready':False,'context':{k:{'status':'incomplete_interval'}for k in ['tenures','committee_memberships','party_memberships','district_memberships']}};return r,c
 def test_literal_count_does_not_require_invented_history(self):r,c=self.fixture();self.assertEqual(g.classify(r,c),[])
 def test_outside_tenure_is_held(self):r,c=self.fixture();c['temporal_conflict_review_required']=True;self.assertIn('outside_recorded_tenure',g.classify(r,c))
 def test_context_status_cannot_be_bypassed_by_false_flag(self):r,c=self.fixture();c['context']['tenures']['status']='outside_recorded_intervals';self.assertIn('outside_recorded_tenure',g.classify(r,c))
 def test_unresolved_id_is_held(self):r,c=self.fixture();r['person_id']=c['person_id']=None;self.assertIn('unresolved_person_id',g.classify(r,c))
 def test_invalid_date_is_held(self):r,c=self.fixture();r['date']=c['date']='bad';self.assertIn('missing_or_invalid_activity_date',g.classify(r,c))
 def test_identity_conflict_held(self):r,c=self.fixture();r['identity_status']='identity_evidence_conflict';self.assertIn('conflicting_identity_evidence',g.classify(r,c))
 def test_mismatched_id_rejected(self):
  r,c=self.fixture();c['person_id']='other'
  with self.assertRaisesRegex(ValueError,'mismatch'):g.classify(r,c)
 def test_missing_flag_rejected(self):
  r,c=self.fixture();del c['group_comparison_ready']
  with self.assertRaisesRegex(ValueError,'flag'):g.classify(r,c)
 def test_forged_group_readiness_rejected(self):
  r,c=self.fixture();c['group_comparison_ready']=True
  with self.assertRaisesRegex(ValueError,'readiness'):g.classify(r,c)
 def test_forged_committee_readiness_rejected(self):
  r,c=self.fixture();c['committee_opportunity_ready']=True
  with self.assertRaisesRegex(ValueError,'readiness'):g.classify(r,c)

 def test_unknown_identity_basis_not_silently_counted(self):r,c=self.fixture();r['identity_status']='unknown_future_status';self.assertIn('unrecognized_identity_basis',g.classify(r,c))
