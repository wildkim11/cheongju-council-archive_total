import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compare_topic_reviews as c
import test_topic_review_materials as fixtures
class ComparisonTests(unittest.TestCase):
 def fixture(self):
  h=fixtures.TopicReviewTests();r=h.record();b=h.book();a=h.annotation(r);a.update(case_id='case',codebook_sha256='hash',full_text_read=True,review_method='independent',reviewed_at='2026-11-04',change_reason=None)
  self.args=({'case':{'activity_id':r['activity_id']}},{r['activity_id']:r},{'case':copy.deepcopy(a)},b,'hash');return a
 def run_reviews(self,rows):return c.compare(rows,*self.args)
 def test_independent_agreement_is_not_gold_or_accuracy(self):
  a=self.fixture();r=self.run_reviews([a]);self.assertEqual(r['agreements'],1);self.assertFalse(r['accuracy_computed']);self.assertFalse(r['gold_reference_created'])
 def test_ai_draft_cannot_be_human_review(self):
  a=self.fixture();a['review_origin']='automated';self.assertEqual(self.run_reviews([a])['accepted_reviews'],0)
 def test_requires_full_read_and_method(self):
  a=self.fixture();a['full_text_read']=False;self.assertEqual(len(self.run_reviews([a])['held']),1)
 def test_duplicate_holds_both(self):
  a=self.fixture();r=self.run_reviews([a,a]);self.assertEqual(r['accepted_reviews'],0);self.assertEqual(len(r['held']),2)
 def test_stale_case_held(self):
  a=self.fixture();a['case_id']='stale';self.assertEqual(len(self.run_reviews([a])['held']),1)
 def test_source_quote_tampering_held(self):
  a=self.fixture();a['evidence_spans'][0]['quote']='wrong';self.assertEqual(len(self.run_reviews([a])['held']),1)
 def test_disagreement_requires_reason(self):
  a=self.fixture();a.update(decision='no_policy',topic_ids=[],evidence_spans=[]);self.assertEqual(self.run_reviews([a])['accepted_reviews'],0);a['change_reason']='본문 전체 검토에서 정책 요구로 보기 어려움';r=self.run_reviews([a]);self.assertEqual(r['disagreements'],1);self.assertTrue(r['reviews'][0]['removed_topic_ids'])
 def test_empty_reviews_are_not_completion(self):
  self.fixture();r=self.run_reviews([]);self.assertEqual(r['accepted_reviews'],0);self.assertFalse(r['accuracy_computed'])
if __name__=='__main__':unittest.main()
