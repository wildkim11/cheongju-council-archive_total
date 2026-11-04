import json,gzip,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_topic_review_drafts as d,build_topic_review_materials as m
from process_meeting_segments import encoded,write_json
import test_topic_review_materials as fixtures
class TopicDraftTests(unittest.TestCase):
 def fixture(self,root):
  helper=fixtures.TopicReviewTests();record=helper.record();helper.fixture(root,[record]);m.build(root);template=json.loads(gzip.decompress((root/'exports/topic-review/development_sample.jsonl.gz').read_bytes()).splitlines()[0]);a=helper.annotation(record);a.update(schema='cheongju-topic-annotation-draft/1',annotation_id='draft-1',case_id=template['case_id'],codebook_sha256=template['codebook_sha256'],status='draft',review_origin='automated',reviewer_id=None,generator='test-model',human_review_required=True,human_review_status='pending',evaluation_reference_eligible=False,topic_set_complete=False,reading_scope='selected passages only');folder=root/'archive/analysis_annotations/v1';folder.mkdir(parents=True);path=folder/'ai_draft_test.jsonl';path.write_bytes(encoded(a));return record,helper.book(),a,path
 def test_draft_is_evidence_checked_but_not_human_reference(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);r,book,a,path=self.fixture(root);before=path.read_bytes();report=d.build(root);self.assertEqual(report['source_integrity_valid_drafts'],1);self.assertEqual(report['human_reviews_completed'],0);self.assertFalse(report['semantic_validation_complete']);self.assertEqual(path.read_bytes(),before)
   with self.assertRaisesRegex(ValueError,'human review not completed'):m.validate_annotation(a,r,book,a['codebook_sha256'])
 def test_tampered_quote_is_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);r,book,a,path=self.fixture(root);a['evidence_spans'][0]['quote']='다른문장';path.write_bytes(encoded(a));report=d.build(root);self.assertEqual(report['held_drafts'],1);self.assertEqual(report['source_integrity_valid_drafts'],0)
 def test_stale_source_is_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);r,book,a,path=self.fixture(root);a['member_text_sha256']='old';path.write_bytes(encoded(a));self.assertEqual(d.build(root)['held_drafts'],1)
 def test_changed_codebook_is_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);r,book,a,path=self.fixture(root);book['version']='v2';write_json(root/'config/policy_topics_v1.json',book);m.build(root);self.assertEqual(d.build(root)['held_drafts'],1)
 def test_duplicate_current_proposals_not_arbitrarily_selected(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);r,book,a,path=self.fixture(root);path.write_bytes(encoded(a)+encoded({**a,'annotation_id':'draft-2'}));report=d.build(root);self.assertEqual(report['held_drafts'],2);self.assertEqual(report['source_integrity_valid_drafts'],0)
 def test_draft_cannot_claim_human_or_evaluation_readiness(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);r,book,a,path=self.fixture(root)
   for key,value in [('review_origin','human'),('evaluation_reference_eligible',True),('topic_set_complete',True)]:
    bad={**a,key:value}
    with self.assertRaisesRegex(ValueError,'provenance/status'):d.validate_draft(bad,r,book,a['codebook_sha256'])
 def test_altered_case_is_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);r,book,a,path=self.fixture(root);a['case_id']='other';path.write_bytes(encoded(a));self.assertEqual(d.build(root)['held_drafts'],1)
 def test_immutable_external_codebook_in_candidate(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);r,book,a,path=self.fixture(root);path=root/'policy.json';(root/'config/policy_topics_v1.json').rename(path);self.assertEqual(d.build(root,codebook_path=path)['source_integrity_valid_drafts'],1)
if __name__=='__main__':unittest.main()
