import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_member_text_inputs import reasons_for
class MemberTextInputTests(unittest.TestCase):
 def test_split_does_not_promote_unresolved_identity(self):self.assertEqual(reasons_for({'base_count_eligible':False,'hold_reasons':['unresolved_person_id']},1),['unresolved_person_id'])
 def test_eligible_count_without_content_is_held(self):self.assertEqual(reasons_for({'base_count_eligible':True,'hold_reasons':[]},0),['member_text_boundary_unverified'])
 def test_unique_content_and_gate_required(self):self.assertEqual(reasons_for({'base_count_eligible':True,'hold_reasons':[]},1),[])
 def test_multiple_content_proofs_are_held(self):self.assertEqual(reasons_for({'base_count_eligible':True,'hold_reasons':[]},2),['ambiguous_member_text_source'])
 def test_tenure_conflict_is_preserved(self):self.assertEqual(reasons_for({'base_count_eligible':False,'hold_reasons':['outside_recorded_tenure']},1),['outside_recorded_tenure'])
 def test_contradictory_gate_rejected(self):
  with self.assertRaises(ValueError):reasons_for({'base_count_eligible':True,'hold_reasons':['unresolved_person_id']},1)
if __name__=='__main__':unittest.main()
