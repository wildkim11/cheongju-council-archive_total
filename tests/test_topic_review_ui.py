import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_topic_review_ui as ui,build_topic_review_drafts as drafts
import test_topic_review_drafts as fixtures
class TopicReviewUITests(unittest.TestCase):
 def fixture(self,root):
  fixtures.TopicDraftTests().fixture(root);drafts.build(root);(root/'web').mkdir();(root/'web/topic_review.html').write_text((ui.ROOT/'web/topic_review.html').read_text())
 def test_packet_contains_source_and_safe_payload(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);p=ui.build(root);s=p.read_text();self.assertIn('application/json',s);self.assertNotIn('/*REVIEW_PAYLOAD*/',s);self.assertIn('완료한 검토 내려받기',s)
 def test_tampered_release_rejected(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);(root/'exports/topic-review/development_sample.jsonl.gz').write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'hash/size'):ui.build(root)
 def test_stale_codebook_rejected(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);p=root/'config/policy_topics_v1.json';p.write_bytes(p.read_bytes()+b' ')
   with self.assertRaisesRegex(ValueError,'snapshot'):ui.build(root)
 def test_candidate_uses_immutable_config_and_template(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);book=root/'book.json';template=root/'template.html';(root/'config/policy_topics_v1.json').rename(book);(root/'web/topic_review.html').rename(template);self.assertTrue(ui.build(root,codebook_path=book,template_path=template).exists())
if __name__=='__main__':unittest.main()
