import gzip,hashlib,json,shutil,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from extract_attachment_text import build,encoded,sha,verify_document
VERSIONS={'pdfinfo':'test fixture','pdftotext':'test fixture'}
URL='https://council.cheongju.go.kr/paper_down.html?number=1&gb=qna'
def pages(text='쪽별 추출문'):
 return [{'page':1,'text':text,'text_sha256':sha(text.encode()),'nonspace_characters':len(''.join(text.split())),'status':'machine_text_unreviewed'if text.strip()else'needs_ocr_or_visual_review','semantic_verified':False}]
class AttachmentTextTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  raw=b'%PDF-1.4\nfixture';self.digest=sha(raw);self.rel='archive/attachments/'+self.digest+'.bin';self.put(self.rel,raw)
  self.queue={URL:{'status':'downloaded','path':self.rel,'sha256':self.digest,'bytes':len(raw)}};self.save_queue()
  self.source=[{'source_id':'1','title':'질문자료','detail_url':'https://council.cheongju.go.kr/content/activity/questionLetter.html?number=1','question_file_url':URL}];self.save_source()
 def put(self,path,raw):
  p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 def save_queue(self):self.put('reports/automatic/attachments.json',encoded(self.queue))
 def save_source(self):
  raw=b''.join(encoded(r)for r in self.source);self.put('exports/analyzer/written_questions.jsonl',raw);self.put('exports/analyzer/manifest.json',encoded({'schema':'cheongju-council-archive-analyzer-export/0.1','datasets':{'written_questions':{'path':'exports/analyzer/written_questions.jsonl','rows':len(self.source),'sha256':sha(raw)}}}))
 def build(self,extractor=lambda p:pages(),**kw):return build(self.root,extractor=extractor,versions=VERSIONS,**kw)
 def manifest(self):return json.loads((self.root/'exports/attachment-text/manifest.json').read_text())
 def test_page_coordinates_hash_and_no_semantic_promotion(self):
  r=self.build();m=self.manifest();entry=m['files'][self.digest];raw=(self.root/'exports/attachment-text'/entry['file']).read_bytes();doc=json.loads(gzip.decompress(raw))
  self.assertEqual(sha(raw),entry['sha256']);self.assertEqual(doc['pages'][0]['page'],1);self.assertFalse(doc['semantic_verified']);self.assertFalse(doc['member_attribution_allowed']);self.assertEqual(r['human_reviewed_pages'],0);self.assertEqual(m['urls'][0]['source_refs'][0]['source_row_1based'],1)
 def test_blank_pages_are_not_text_success(self):
  r=self.build(lambda p:pages(' \n'));self.assertEqual(r['pages_needing_ocr_or_visual_review'],1);self.assertEqual(r['pages_with_text'],0);self.assertEqual(self.manifest()['files'][self.digest]['text_status'],'needs_ocr')
 def test_images_wait_for_ocr_without_pdf_parser(self):
  raw=b'\xff\xd8\xfffixture';digest=sha(raw);rel='archive/attachments/'+digest+'.bin';self.put(rel,raw);self.queue[URL].update(path=rel,sha256=digest,bytes=len(raw));self.save_queue()
  r=self.build(lambda p:self.fail('image entered PDF parser'));self.assertEqual(r['text_status_counts']['needs_ocr'],1)
 def test_pending_and_blocked_are_not_extracted(self):
  self.queue={URL:{'status':'pending'},URL.replace('qna','ans'):{'status':'blocked'}};self.save_queue();r=self.build(lambda p:self.fail('uncollected source parsed'));self.assertEqual(r['text_status_counts'],{'not_downloaded':2})
 def test_corrupt_original_stops_before_extraction(self):
  self.put(self.rel,b'%PDF changed')
  with self.assertRaisesRegex(ValueError,'hash/size'):self.build(lambda p:self.fail('corrupt file parsed'))
 def test_unsafe_original_path_is_rejected(self):
  self.queue[URL]['path']='archive/attachments/../../escape';self.save_queue()
  with self.assertRaisesRegex(ValueError,'unsafe'):self.build()
 def test_source_manifest_corruption_is_rejected(self):
  self.put('exports/analyzer/written_questions.jsonl',b'{}\n')
  with self.assertRaisesRegex(ValueError,'dataset hash'):self.build()
 def test_same_file_multiple_urls_is_parsed_once(self):
  self.queue[URL.replace('qna','ans')]=dict(self.queue[URL]);self.save_queue();called=[];r=self.build(lambda p:(called.append(p)or pages()));self.assertEqual(len(called),1);self.assertEqual(r['downloaded_urls'],2);self.assertEqual(r['unique_files'],1)
 def test_cached_page_tampering_fails_closed(self):
  self.build();m=self.manifest();self.put('exports/attachment-text/'+m['files'][self.digest]['file'],b'altered')
  with self.assertRaisesRegex(ValueError,'cached attachment text hash'):self.build()
 def test_valid_cache_skips_reextraction(self):
  self.build();self.build(lambda p:self.fail('unchanged PDF reprocessed'))
 def test_error_is_held_and_explicit_retry_is_possible(self):
  def fail(p):raise ValueError('parser rejected PDF')
  r=self.build(fail);self.assertEqual(r['text_status_counts']['extraction_error'],1);self.build(lambda p:self.fail('failed PDF retried without request'));r=self.build(retry_errors=True);self.assertEqual(r['extracted_pdf_files'],1)
 def test_source_join_is_exact_url_not_name_or_substring(self):
  self.source[0]['question_file_url']=URL+'&other=1';self.source[0]['title']=URL;self.save_source();self.build();self.assertEqual(self.manifest()['urls'][0]['source_refs'],[])
  self.source[0]['title']='same person name';self.save_source();self.build();self.assertEqual(self.manifest()['urls'][0]['source_refs'],[])
 def test_document_cannot_claim_member_or_semantic_approval(self):
  doc={'schema':'cheongju-attachment-page-text/1','source_sha256':self.digest,'semantic_verified':False,'member_attribution_allowed':True,'pages':pages()}
  with self.assertRaises(ValueError):verify_document(doc,self.digest)
 @unittest.skipUnless(shutil.which('pdftotext')and shutil.which('pdfinfo'),'Poppler integration')
 def test_preserved_real_pdf_is_parsed_pagewise(self):
  root=Path(__file__).resolve().parents[1];p=root/'archive/attachments/f2accccba595a739ce52d7a48258674df81b30a42e0ad24fa088a655e7b93e68.bin'
  if not p.exists():self.skipTest('preserved one-page PDF is unavailable')
  from extract_attachment_text import extract_pdf
  result=extract_pdf(p);self.assertEqual(len(result),1);self.assertGreater(result[0]['nonspace_characters'],0);self.assertFalse(result[0]['semantic_verified'])
if __name__=='__main__':unittest.main()
