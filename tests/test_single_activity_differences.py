import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_single_activity_differences import classify
class SingleDifferenceTests(unittest.TestCase):
 def test_stage_note_is_exact(self):
  self.assertEqual(classify('','(발언제한시간초과로마이크중단)(마이크중단이후발언한부분)'),'recording_stage_note')
  self.assertEqual(classify('','(발언제한시간초과로마이크중단)정책'),'word_or_particle_difference')
 def test_redaction(self):self.assertEqual(classify('배근','○○'),'redacted_person_name')
 def test_latin_annotation(self):self.assertEqual(classify('','(TaskForce)'),'parenthesized_latin_annotation')
 def test_numeric_boundary(self):self.assertEqual(classify(' ',''),'numeric_whitespace_boundary')
 def test_middle_dot_is_not_word(self):self.assertEqual(classify('․','ㆍ'),'symbol_or_middle_dot')
 def test_word_not_auto_corrected(self):self.assertEqual(classify('채','체'),'word_or_particle_difference')
 def test_question_tail_requires_dataset_and_edge(self):
  self.assertEqual(classify('답변문장','',True,'city_questions'),'question_answer_tail_review')
  self.assertEqual(classify('답변문장','',False,'city_questions'),'word_or_particle_difference')
if __name__=='__main__':unittest.main()
