import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_attachment_downloads as a
class AttachmentDownloadAuditTests(unittest.TestCase):
 def fixture(self,root):
  raw=b'%PDF-1.4\nheader fixture only';p=root/'archive/attachments/one.bin';p.parent.mkdir(parents=True);p.write_bytes(raw);row={'status':'downloaded','path':'archive/attachments/one.bin','sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)};q={'https://council.cheongju.go.kr/paper_down.html?number=29&gb=qna':row};return p,q
 def write(self,root,q):
  p=root/'reports/automatic/attachments.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(q))
 def test_missing_queue_is_not_collected(self):
  with tempfile.TemporaryDirectory()as td:
   r=a.build(Path(td));self.assertEqual(r['status'],'NOT_COLLECTED');self.assertFalse(r['download_queue_complete'])
 def test_download_verified_without_semantic_claims(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);p,q=self.fixture(root);self.write(root,q);r=a.build(root);self.assertEqual(r['verified_downloaded_urls'],1);self.assertTrue(r['download_queue_complete']);self.assertFalse(r['document_semantics_verified']);self.assertFalse(r['document_text_extracted'])
 def test_pending_failed_and_shared_bytes_separate(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);p,q=self.fixture(root);row=next(iter(q.values()));q['https://council.cheongju.go.kr/paper_down.html?number=29&gb=ans']=dict(row);q['https://council.cheongju.go.kr/download.html?fid=1']={'status':'pending'};q['https://council.cheongju.go.kr/download.html?fid=2']={'status':'failed'};self.write(root,q);r=a.build(root);self.assertEqual(r['status_counts'],{'downloaded':2,'pending':1,'failed':1});self.assertEqual(r['unique_verified_files'],1);self.assertEqual(r['remaining_unverified_urls'],2);self.assertFalse(r['download_queue_complete'])
 def test_changed_bytes_are_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);p,q=self.fixture(root);p.write_bytes(b'%PDF tampered');self.write(root,q);r=a.build(root);self.assertEqual(r['status'],'INTEGRITY_ERROR');self.assertEqual(r['verified_downloaded_urls'],0)
 def test_missing_file_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);p,q=self.fixture(root);p.unlink();self.write(root,q);self.assertEqual(a.build(root)['held_records'],1)
 def test_wrong_header_held_even_if_hash_matches(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);p,q=self.fixture(root);p.write_bytes(b'<html>error</html>');row=next(iter(q.values()));row.update(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size);self.write(root,q);self.assertEqual(a.build(root)['held_records'],1)
 def test_unsafe_path_and_host_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);p,q=self.fixture(root);next(iter(q.values()))['path']='../outside';q['https://example.org/download']={'status':'pending'};self.write(root,q);self.assertEqual(a.build(root)['held_records'],2)
 def test_empty_queue_is_not_complete(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.write(root,{});r=a.build(root);self.assertEqual(r['status'],'PASS');self.assertFalse(r['download_queue_complete'])
if __name__=='__main__':unittest.main()
