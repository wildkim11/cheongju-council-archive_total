import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_question_identity_evidence import assess
class QuestionIdentityEvidenceTests(unittest.TestCase):
 def fixture(self):
  return [{'person_name':'의원','date':'2020-01-01','candidate_person_ids':['p1','p2']},{'date':'2020-01-01','candidates':[{'question_candidate_person_id':'p1','question_speaker_name':'의원'}]},{'date':'2020-01-01','term':2,'council_scope':'scope'},{'person_id':'p1','name':'의원'},[{'person_id':'p1','term':2,'council_scope':'scope','start_date':None,'end_date':None}]]
 def test_term_evidence_not_full_tenure_dates(self):self.assertEqual(assess(*self.fixture()),[])
 def test_other_person_rejected(self):
  v=self.fixture();v[3]['person_id']='other';self.assertIn('person_or_name_mismatch',assess(*v))
 def test_outside_candidates_rejected(self):
  v=self.fixture();v[0]['candidate_person_ids']=['p2'];self.assertIn('outside_existing_identity_candidates',assess(*v))
 def test_date_mismatch_rejected(self):
  v=self.fixture();v[2]['date']='2020-01-02';self.assertIn('date_mismatch',assess(*v))
 def test_term_mismatch_rejected(self):
  v=self.fixture();v[2]['term']=3;self.assertIn('missing_person_scope_term_record',assess(*v))
 def test_scope_mismatch_rejected(self):
  v=self.fixture();v[2]['council_scope']='other';self.assertIn('missing_person_scope_term_record',assess(*v))
if __name__=='__main__':unittest.main()
