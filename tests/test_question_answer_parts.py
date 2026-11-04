import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_question_answer_parts import split_candidate
class QuestionAnswerPartsTests(unittest.TestCase):
 def test_exact_split_preserves_original_whitespace(self):
  q='의원 질문입니다. '*20;a='시장 답변입니다. '*20;body=q+'\n\n'+a
  result=split_candidate(body,q,a)
  self.assertEqual(result['question_text']+result['answer_text'],body)
  self.assertTrue(result['answer_text'].lstrip().startswith('시장'))
 def test_changed_digit_is_not_ignored(self):
  q='예산 1234원 질문 '*20;a='답변입니다. '*20
  self.assertIsNone(split_candidate(q.replace('1234','1235')+a,q,a))
 def test_partial_question_is_rejected(self):
  q='의원 질문입니다. '*20;a='시장 답변입니다. '*20
  self.assertIsNone(split_candidate(q[5:]+a,q,a))
 def test_unverified_answer_tail_is_rejected(self):
  q='의원 질문입니다. '*20;a='시장 답변입니다. '*20
  self.assertIsNone(split_candidate(q+a,q,'다른 답변입니다. '*20))
 def test_repeated_answer_is_ambiguous(self):
  q='의원 질문입니다. '*20;a='시장 답변입니다. '*20
  self.assertIsNone(split_candidate(q+a,q,a+a))
 def test_numeric_whitespace_stays_significant(self):
  q='질문 12 34입니다. '*20;a='답변입니다. '*20
  self.assertIsNone(split_candidate(q.replace('12 34','1234')+a,q,a))
if __name__=='__main__':unittest.main()
