import gzip,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import extract_attachment_text as base
import ocr_attachment_pages as ocr
URL='https://council.cheongju.go.kr/gtb_download.php?gtid=debate&fid=1'
ENGINE={'name':'test_ocr','script_sha256':'a'*64,'settings':ocr.SETTINGS}
def result(text='한글 인식 시험'):
 return {'raster':{'width':100,'height':100,'mode':'L','pixel_sha256':'b'*64},'text':text,'text_sha256':base.sha(text.encode()),'words':[]if not text.strip()else[{'text':'한글','box':[1,2,10,10],'tesseract_confidence':51.2}]}
class OCRTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);raw=b'\xff\xd8\xfffixture';self.sha=base.sha(raw);self.path='archive/attachments/'+self.sha+'.bin';self.put(self.path,raw);self.queue={URL:{'status':'downloaded','path':self.path,'sha256':self.sha,'bytes':len(raw)}};self.put('reports/automatic/attachments.json',base.encoded(self.queue));self.source={'source_id':'1','title':'공통 토론회','attachments':[URL]};self.sources();self.extract()
 def put(self,path,content):
  p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
 def sources(self):
  raw=base.encoded(self.source);self.put('exports/analyzer/debates.jsonl',raw);self.put('exports/analyzer/manifest.json',base.encoded({'schema':'cheongju-council-archive-analyzer-export/0.1','datasets':{'debates':{'path':'exports/analyzer/debates.jsonl','rows':1,'sha256':base.sha(raw)}}}))
 def extract(self):return base.build(self.root,extractor=lambda p:[],versions={'pdfinfo':'test','pdftotext':'test'})
 def build(self,recognizer=lambda *args:result(),**kw):return ocr.build(self.root,engine=ENGINE,recognizer=recognizer,**kw)
 def manifest(self):return json.loads((self.root/'exports/attachment-ocr/manifest.json').read_text())
 def test_image_coordinates_source_and_unreviewed_flags(self):
  r=self.build();m=self.manifest();i=m['items'][0];d=json.loads(gzip.decompress((self.root/'exports/attachment-ocr'/i['file']).read_bytes()));self.assertEqual(d['task']['page_coordinate'],'single_image_1');self.assertEqual(d['task']['source_links'][0]['url'],URL);self.assertFalse(d['member_attribution_allowed']);self.assertFalse(d['semantic_verified']);self.assertFalse(d['analysis_usable']);self.assertEqual(r['human_reviewed_pages'],0);self.assertFalse(r['confidence_is_accuracy'])
 def test_no_text_is_not_confirmed_blank_page(self):
  r=self.build(lambda *args:result(''));self.assertEqual(r['status_counts']['ocr_no_text_unreviewed'],1);self.assertEqual(r['semantic_verified_pages'],0)
 def test_original_tamper_blocks_before_recognition(self):
  self.put(self.path,b'changed')
  with self.assertRaisesRegex(ValueError,'hash/size'):self.build(lambda *args:self.fail('changed source used'))
 def test_text_hash_and_word_bounds_are_enforced(self):
  for mutate in [lambda r:r.update(text_sha256='0'*64),lambda r:r['words'][0].update(box=[99,99,20,20]),lambda r:r['words'][0].update(tesseract_confidence=101)]:
   r=result();mutate(r)
   with self.assertRaises(ValueError):ocr.validate_result(r)
 def test_valid_cache_avoids_repeated_ocr(self):
  self.build();self.build(lambda *args:self.fail('same page OCR rerun'))
 def test_source_context_updates_without_recognizing_again(self):
  self.build();self.source['title']='새 원문 제목';self.sources();self.extract();self.build(lambda *args:self.fail('metadata-only update OCR rerun'));self.assertEqual(self.manifest()['items'][0]['task']['source_links'][0]['source_refs'][0]['title'],'새 원문 제목')
 def test_corrupt_cached_result_is_rejected(self):
  self.build();m=self.manifest();self.put('exports/attachment-ocr/'+m['items'][0]['file'],b'corrupt')
  with self.assertRaisesRegex(ValueError,'cache integrity'):self.build()
 def test_errors_held_until_explicit_retry(self):
  def fail(*args):raise ValueError('recognizer failed')
  self.assertEqual(self.build(fail)['status_counts']['ocr_error_held'],1);self.build(lambda *args:self.fail('error retried'));self.assertEqual(self.build(retry_errors=True)['status_counts']['machine_ocr_unreviewed'],1)
 def test_page_budget_leaves_explicit_pending(self):
  old=ocr.MAX_NEW;ocr.MAX_NEW=0
  try:self.assertEqual(self.build()['status_counts']['ocr_pending'],1)
  finally:ocr.MAX_NEW=old
 def test_semantic_or_member_promotion_is_rejected(self):
  task=ocr.inputs(self.root)[1][0];d={'schema':'cheongju-attachment-page-ocr/1','task':task,'engine':ENGINE,'result':result(),'status':'machine_ocr_unreviewed','semantic_verified':True,'member_attribution_allowed':False}
  with self.assertRaises(ValueError):ocr.verify_document(d,task,ENGINE)
 def test_missing_korean_model_does_not_fall_back_to_english(self):
  if not shutil.which('tesseract'):self.skipTest('tesseract not installed')
  with tempfile.TemporaryDirectory()as temp:
   try:
    with self.assertRaisesRegex(RuntimeError,'kor'):ocr.environment(Path(temp))
   except ImportError:self.skipTest('Pillow unavailable')
 @unittest.skipUnless(shutil.which('tesseract'),'OCR integration')
 def test_real_ocr_can_use_model_directory_without_config_files(self):
  try:_,models=ocr.environment()
  except (RuntimeError,ImportError):self.skipTest('Korean OCR models unavailable')
  # Temp model directory deliberately excludes configs/txt and configs/tsv.
  p=Path(__file__).resolve().parents[1]/'archive/attachments/c4beaedaebd812014d76c93dabbb21a085669ffcb31f7786941de94d57d32308.bin'
  if not p.exists():self.skipTest('preserved image unavailable')
  with tempfile.TemporaryDirectory()as temp:
   for lang in ['kor','eng']:shutil.copyfile(models/(lang+'.traineddata'),Path(temp)/(lang+'.traineddata'))
   r=ocr.recognize(p,'jpeg_header',1,Path(temp));self.assertEqual(r['text_sha256'],base.sha(r['text'].encode()))
if __name__=='__main__':unittest.main()
