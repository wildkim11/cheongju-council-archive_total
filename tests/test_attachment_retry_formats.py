import io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import automated_collection as a
from attachment_formats import signature
import audit_attachment_downloads as audit
class AttachmentRetryFormatTests(unittest.TestCase):
 URL='https://council.cheongju.go.kr/gtb_download.php?gtid=debate&fid=11820'
 def fixture(self,root,row=None):a.save_json(root/'reports/automatic/attachments.json',{self.URL:row or{'status':'pending','attempts':0}})
 def queue(self,root):return json.loads((root/'reports/automatic/attachments.json').read_text())[self.URL]
 def download(self,root,payload,**kw):
  opener=MagicMock();opener.open.return_value=io.BytesIO(payload)
  with patch.object(a.urllib.request,'build_opener',return_value=opener),patch.object(a.time,'sleep'):
   result=a.download_attachments(root,**kw)
  return result,opener
 def test_failed_jpeg_can_retry_and_pass_hash_audit(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,{'status':'failed','attempts':1,'error':'unexpected document signature; not counted as downloaded'});r,_=self.download(root,b'\xff\xd8\xff\xe0fixture',retry_only=True);row=self.queue(root);self.assertEqual(r['downloaded_total'],1);self.assertEqual(row['container_header'],'jpeg_header');self.assertNotIn('error',row);self.assertEqual(audit.build(root)['verified_downloaded_urls'],1)
 def test_png_supported_without_accepting_html(self):
  self.assertEqual(signature(b'\x89PNG\r\n\x1a\nfixture'),'png_header');self.assertIsNone(signature(b'<html>error</html>'))
 def test_html_response_remains_failed(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);r,_=self.download(root,b'<html>error</html>');self.assertEqual(r['failed_total'],1);self.assertEqual(r['downloaded_total'],0);self.assertIn('next_retry_at',self.queue(root))
 def test_oversize_blocked_without_repeat_http(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);r,_=self.download(root,b'%PDF'+b'x'*20,max_bytes=8);self.assertEqual(r['blocked_total'],1);self.assertNotIn('next_retry_at',self.queue(root));r,opener=self.download(root,b'%PDF'+b'x'*20,max_bytes=8);self.assertEqual(r['attempted'],0);opener.open.assert_not_called()
 def test_legacy_oversize_failure_migrates_without_request(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,{'status':'failed','attempts':1,'error':'attachment exceeds per-file archive limit','next_retry_at':'2099-01-01T00:00:00Z'});r,opener=self.download(root,b'',retry_only=True);self.assertEqual(r['blocked_total'],1);self.assertEqual(r['failed_total'],0);opener.open.assert_not_called();self.assertEqual(self.queue(root)['hold_reason'],'size_limit_exceeded')
 def test_size_recovery_only_reopens_lower_limit_holds(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   self.fixture(root,{'status':'blocked','attempts':1,'hold_reason':'size_limit_exceeded','max_bytes':8})
   raw=b'%PDF'+b'x'*12
   result,_=self.download(root,raw,max_bytes=12,oversize_only=True)
   self.assertEqual(result['blocked_total'],1);self.assertEqual(self.queue(root)['max_bytes'],12)
   result,opener=self.download(root,raw,max_bytes=12,oversize_only=True)
   self.assertEqual(result['attempted'],0);opener.open.assert_not_called()
   result,_=self.download(root,raw,max_bytes=16,oversize_only=True)
   self.assertEqual(result['downloaded_total'],1);self.assertNotIn('hold_reason',self.queue(root))
   self.assertNotIn('max_bytes',self.queue(root));self.assertEqual(audit.build(root)['verified_downloaded_urls'],1)
 def test_blocked_queue_is_not_full_coverage(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,{'status':'blocked','attempts':1,'hold_reason':'size_limit_exceeded'});r=audit.build(root);self.assertEqual(r['status'],'PASS');self.assertEqual(r['status_counts']['blocked'],1);self.assertFalse(r['download_queue_complete']);self.assertEqual(r['remaining_unverified_urls'],1)
if __name__=='__main__':unittest.main()
