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

class MultiReviewerTests(unittest.TestCase):
 def setUp(self):
  self.helper=ComparisonTests();self.a=self.helper.fixture()
 def run_reviews(self,rows):return self.helper.run_reviews(rows)
 def second(self):
  b=copy.deepcopy(self.a);b['reviewer_id']='second';return b
 def test_independent_same_decision_not_accuracy(self):
  s=self.run_reviews([self.a,self.second()])['reviewer_comparison'];self.assertEqual(s['self_reported_independent_pairs'],1);self.assertEqual(s['disagreeing_pairs'],0);self.assertIsNone(s['agreement_rate']);self.assertIsNone(s['reliability_coefficient']);self.assertFalse(s['majority_vote_applied'])
 def test_topic_and_decision_differences_preserved(self):
  b=self.second();b.update(decision='no_policy',topic_ids=[],evidence_spans=[],change_reason='별도 판단');s=self.run_reviews([self.a,b])['reviewer_comparison'];pair=s['cases'][0]['pairs'][0];self.assertTrue(pair['decision_differs']);self.assertTrue(pair['topic_ids_only_a']);self.assertEqual(s['disagreeing_pairs'],1);self.assertTrue(s['cases'][0]['requires_resolution'])
 def test_ai_assisted_pair_is_separate(self):
  b=self.second();b['review_method']='ai_assisted';s=self.run_reviews([self.a,b])['reviewer_comparison'];self.assertEqual(s['pairs_including_ai_assistance'],1);self.assertEqual(s['self_reported_independent_pairs'],0)
 def test_two_ambiguous_responses_are_unresolved(self):
  a=copy.deepcopy(self.a);b=self.second()
  for r in [a,b]:r.update(decision='ambiguous',topic_ids=[],evidence_spans=[],change_reason='해석 보류')
  s=self.run_reviews([a,b])['reviewer_comparison'];self.assertEqual(s['cases'][0]['pairs'][0]['outcome'],'unresolved');self.assertTrue(s['cases'][0]['requires_resolution']);self.assertEqual(s['pairs_including_ambiguous'],1)
 def test_single_reviewer_has_no_overlap(self):
  s=self.run_reviews([self.a])['reviewer_comparison'];self.assertEqual(s['status'],'insufficient_overlap');self.assertEqual(s['reviewer_pair_comparisons'],0)
 def test_malformed_records_are_held_without_losing_valid_rows(self):
  r=self.run_reviews([None,[],{'case_id':[],'reviewer_id':'x'},self.a]);self.assertEqual(r['accepted_reviews'],1);self.assertEqual(len(r['held']),3)
 def test_invalid_timestamp_held(self):
  a=copy.deepcopy(self.a);a['reviewed_at']='not a date';self.assertEqual(len(self.run_reviews([a])['held']),1)
 def test_empty_is_no_data_not_perfect_agreement(self):
  s=self.run_reviews([])['reviewer_comparison'];self.assertEqual(s['status'],'no_reviews');self.assertIsNone(s['agreement_rate'])

 def test_malformed_json_lines_preserve_other_reviews(self):
  import tempfile,json
  import build_topic_review_drafts as drafts
  import test_topic_review_drafts as df
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);record,book,a,path=df.TopicDraftTests().fixture(root);drafts.build(root);a.update(status='completed',review_origin='human',reviewer_id='test',full_text_read=True,review_method='independent',reviewed_at='2026-11-04');source=root/'human.jsonl';source.write_text('{broken\nnull\n'+json.dumps(a)+'\n');r=c.build(root,source);self.assertEqual(r['accepted_reviews'],1);self.assertEqual(len(r['held']),2)
 def test_peer_assistance_is_not_mislabelled_as_ai(self):
  b=self.second();b['review_method']='peer_assisted';b['peer_review_seen']=True;s=self.run_reviews([self.a,b])['reviewer_comparison'];self.assertEqual(s['pairs_including_peer_assistance'],1);self.assertEqual(s['pairs_including_ai_assistance'],0);self.assertEqual(s['self_reported_independent_pairs'],0)
 def test_peer_exposure_cannot_claim_independent(self):
  self.a['peer_review_seen']=True;self.assertEqual(self.run_reviews([self.a])['accepted_reviews'],0)
if __name__=='__main__':unittest.main()
