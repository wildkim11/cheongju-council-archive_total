import gzip,importlib.util,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import extract_attachment_text as base
import ocr_attachment_pages as ocr
import build_ocr_review_assets as assets
import build_ocr_review_packet as packet
class OCRReviewCoreTests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('node'),'Node required')
 def test_review_state_and_atomic_restore(self):
  r=subprocess.run(['node',str(ROOT/'tests/ocr_review_core.cjs')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
@unittest.skipUnless(importlib.util.find_spec('PIL'),'Pillow required')
class OCRReviewPacketTests(unittest.TestCase):
 def setUp(self):
  from PIL import Image
  import io
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.image=Image.new('L',(3,3),128);buffer=io.BytesIO();self.image.save(buffer,format='PNG');raw=buffer.getvalue();digest=base.sha(raw);url='https://council.cheongju.go.kr/gtb_download.php?gtid=debate&fid=1';self.put('archive/attachments/'+digest+'.bin',raw);self.put('reports/automatic/attachments.json',base.encoded({url:{'status':'downloaded','path':'archive/attachments/'+digest+'.bin','sha256':digest,'bytes':len(raw)}}));source=base.encoded({'source_id':'1','title':'검토 출처','attachments':[url]});self.put('exports/analyzer/debates.jsonl',source);self.put('exports/analyzer/manifest.json',base.encoded({'schema':'cheongju-council-archive-analyzer-export/0.1','datasets':{'debates':{'path':'exports/analyzer/debates.jsonl','rows':1,'sha256':base.sha(source)}}}));base.build(self.root,extractor=lambda p:[],versions={'pdfinfo':'test','pdftotext':'test'})
  result={'raster':{'width':3,'height':3,'mode':'L','pixel_sha256':base.sha(self.image.tobytes())},'text':'원문 </script><img src=x>','text_sha256':base.sha('원문 </script><img src=x>'.encode()),'words':[]};ocr.build(self.root,engine={'test':'engine'},recognizer=lambda *a:result)
  for name in ['ocr_review.html','ocr_review_core.js']:self.put('web/'+name,(ROOT/'web'/name).read_bytes())
 def put(self,path,data):
  p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 def build_assets(self):return assets.build(self.root,renderer=lambda *a:self.image.copy())
 def commit(self):
  for args in [['init','-q'],['add','.'],['-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture']]:subprocess.run(['git','-C',str(self.root),*args],check=True,capture_output=True)
  return subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],text=True).strip()
 def test_raster_pixel_mismatch_stops_build(self):
  from PIL import Image
  with self.assertRaisesRegex(ValueError,'pixels differ'):assets.build(self.root,renderer=lambda *a:Image.new('L',(3,3),0))
 def test_source_and_review_flags_preserved(self):
  r=self.build_assets();m=json.loads((self.root/'exports/attachment-ocr-review/manifest.json').read_text());self.assertEqual(r['ready_items'],1);self.assertEqual(m['human_reviewed_pages'],0);self.assertFalse(m['analysis_usable']);self.assertFalse(m['records'][0]['semantic_verified'])
 def test_ocr_document_tampering_is_rejected(self):
  m=json.loads((self.root/'exports/attachment-ocr/manifest.json').read_text());self.put('exports/attachment-ocr/'+m['items'][0]['file'],b'altered')
  with self.assertRaisesRegex(ValueError,'hash mismatch'):self.build_assets()
 def test_offline_packet_escapes_ocr_script_payload(self):
  self.build_assets();commit=self.commit();out=self.root/'review.html';r=packet.build(self.root,out,commit);s=out.read_text();self.assertEqual(r['records'],1);self.assertNotIn('원문 </script><img src=x>',s);self.assertIn('\\u003c/script>',s);self.assertIn('data:image/png;base64,',s)
 def test_packet_requires_committed_snapshot(self):
  self.build_assets();commit=self.commit();self.put('exports/attachment-ocr-review/manifest.json',b'{}')
  with self.assertRaisesRegex(ValueError,'snapshot'):packet.build(self.root,self.root/'review.html',commit)
 def test_png_tamper_is_rejected(self):
  self.build_assets();commit=self.commit();m=json.loads((self.root/'exports/attachment-ocr-review/manifest.json').read_text());self.put('exports/attachment-ocr-review/'+m['records'][0]['image_file'],b'not a PNG')
  with self.assertRaisesRegex(ValueError,'hash mismatch'):packet.build(self.root,self.root/'review.html',commit)
if __name__=='__main__':unittest.main()
