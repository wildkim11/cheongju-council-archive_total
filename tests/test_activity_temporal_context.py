import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_activity_temporal_context as t
class TemporalContextTests(unittest.TestCase):
 def row(self,**changes):return {'person_id':'p','council_scope':'scope','term':4,'start_date':'2026-07-01','end_date':'2026-07-31','period_precision':'exact_date','source_url':'https://council.cheongju.go.kr/test','party':'A',**changes}
 def join(self,rows,when='2026-07-15',dataset='party_memberships',**kwargs):return t.join_history(rows,dataset,kwargs.get('pid','p'),'scope',4,when)
 def test_both_interval_boundaries_inclusive(self):
  for d in ['2026-07-01','2026-07-31']:self.assertEqual(self.join([self.row()],d)['status'],'archived_explicit_interval')
 def test_outside_interval(self):self.assertEqual(self.join([self.row()],'2026-08-01')['status'],'outside_recorded_intervals')
 def test_open_end_is_not_assumed_current(self):self.assertEqual(self.join([self.row(end_date=None)])['status'],'incomplete_interval')
 def test_competing_party_intervals_held(self):self.assertEqual(self.join([self.row(),self.row(party='B')])['status'],'conflicting_facts')
 def test_unknown_extra_period_prevents_complete_context(self):self.assertEqual(self.join([self.row(),self.row(start_date=None,end_date=None)])['status'],'partial_interval_evidence')
 def test_displayed_period_conflict_not_used(self):self.assertEqual(self.join([self.row(displayed_period_conflict=True)])['status'],'incomplete_interval')
 def test_no_name_only_or_wrong_term_join(self):
  self.assertEqual(self.join([self.row()],pid=None)['status'],'missing_identity_term_or_date');self.assertEqual(self.join([self.row(term=3)])['status'],'no_history_records')
 def test_simultaneous_committees_are_not_party_conflicts(self):self.assertEqual(self.join([self.row(label='A'),self.row(label='B')],dataset='committee_memberships')['status'],'archived_explicit_interval')
 def test_reversed_and_invalid_date_held(self):
  self.assertEqual(self.join([self.row(start_date='2026-08-01')])['status'],'incomplete_interval');self.assertEqual(self.join([self.row()],'bad')['status'],'missing_identity_term_or_date')
 def test_nonofficial_or_imprecise_period_not_verified(self):
  for changes in [{'source_url':'https://example.invalid/'},{'period_precision':'term_only'}]:self.assertEqual(self.join([self.row(**changes)])['status'],'incomplete_interval')

 def test_blank_membership_label_never_verifies_context(self):self.assertEqual(self.join([self.row(party=None)])['status'],'incomplete_interval')
 def test_untrusted_outside_date_never_becomes_conflict(self):self.assertEqual(self.join([self.row(source_url='https://example.invalid/')],'2026-08-01')['status'],'incomplete_interval')
