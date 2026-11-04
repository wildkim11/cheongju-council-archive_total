import copy,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import validate_ocr_review_intake as v
def fixture():
 commit='a'*40;packet='b'*64;links=[{'url':'https://council.cheongju.go.kr/gtb_download.php?gtid=debate&fid=1','source_refs':[]}]
 r={'key':'item','source_commit':commit,'task':{'source_sha256':'c'*64,'source_links':links},'raster':{'pixel_sha256':'d'*64},'ocr_document_sha256':'e'*64,'ocr_text':'원래 OCR','ocr_text_sha256':v.digest('원래 OCR'.encode())}
 snapshot={'packet_sha256':packet,'source_commit':commit,'current_commit':commit,'assets_manifest_sha256':'f'*64,'records':{'item':r},'current_records':{'item':copy.deepcopy(r)}}
 row={'schema':'cheongju-ocr-transcription-review/1','record_kind':'user_entered_transcription_review_not_gold','source_commit':commit,'source_links':links,'packet_sha256':packet,'key':'item','source_sha256':'c'*64,'raster_pixel_sha256':'d'*64,'ocr_document_sha256':'e'*64,'status':'checked_transcription','corrected_text':'대조한 전사문','note':'오인식 수정','reviewer':'synthetic tester','source_checked':True,'analysis_usable':False,'semantic_verified':False,'updated_at':'2026-11-04T00:00:00.000Z'}
 return snapshot,row
class OCRIntakeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dir=Path(self.tmp.name);self.snapshot,self.row=fixture()
 def file(self,rows):
  p=self.dir/'review.jsonl';p.write_text('\n'.join(json.dumps(r,ensure_ascii=False)for r in rows));return p
 def intake(self,rows):
  with patch.object(v,'load_packet',return_value=self.snapshot):return v.intake('packet.html',self.file(rows),self.dir)
 def test_valid_transcription_is_stored_without_approval(self):
  r=self.intake([self.row]);self.assertEqual(r['status'],'VALIDATED_NOT_APPROVED');self.assertEqual(r['declared_checked_transcriptions'],1);self.assertEqual(r['analysis_usable_records'],0);self.assertFalse(r['reviewer_identity_authenticated'])
 def test_missing_input_stays_zero(self):
  with patch.object(v,'load_packet',return_value=self.snapshot):r=v.intake('packet.html',root=self.dir)
  self.assertEqual(r['status'],'NO_USER_INPUT');self.assertEqual(r['input_records'],0);self.assertEqual(r['validated_records'],[])
 def test_duplicate_ids_hold_entire_batch(self):
  self.snapshot['records']['other']={**self.snapshot['records']['item'],'key':'other'}
  r=self.intake([self.row,self.row]);self.assertEqual(r['status'],'HELD_INVALID_INPUT');self.assertEqual(r['validated_records'],[])
 def test_one_bad_row_does_not_partially_accept_good_rows(self):
  self.snapshot['records']['other']={**self.snapshot['records']['item'],'key':'other'};bad={**self.row,'key':'other','analysis_usable':True}
  r=self.intake([self.row,bad]);self.assertEqual(r['status'],'HELD_INVALID_INPUT');self.assertEqual(r['validated_records'],[]);self.assertEqual(r['declared_checked_transcriptions'],0)
 def test_source_version_and_original_links_are_bound(self):
  for field,value in [('source_commit','1'*40),('source_sha256','2'*64),('raster_pixel_sha256','3'*64),('ocr_document_sha256','4'*64),('packet_sha256','5'*64),('source_links',[])]:
   with self.subTest(field=field):self.assertEqual(self.intake([{**self.row,field:value}])['status'],'HELD_INVALID_INPUT')
 def test_current_snapshot_changes_are_held(self):
  self.snapshot['current_records']['item']['ocr_document_sha256']='6'*64;self.assertEqual(self.intake([self.row])['status'],'HELD_INVALID_INPUT')
 def test_checked_status_needs_actual_fields(self):
  for field,value in [('reviewer',''),('source_checked',False),('corrected_text',' '),('updated_at',None)]:
   with self.subTest(field=field):self.assertEqual(self.intake([{**self.row,field:value}])['status'],'HELD_INVALID_INPUT')
 def test_hold_requires_reason(self):
  self.assertEqual(self.intake([{**self.row,'status':'held','note':''}])['status'],'HELD_INVALID_INPUT');r=self.intake([{**self.row,'status':'held','note':'사진 오인식 후보'}]);self.assertEqual(r['declared_status_counts'],{'held':1});self.assertEqual(r['analysis_usable_records'],0)
 def test_unreviewed_cannot_hide_edits(self):
  row={**self.row,'status':'unreviewed','reviewer':'','note':'','source_checked':False,'updated_at':None};self.assertEqual(self.intake([row])['status'],'HELD_INVALID_INPUT');row['corrected_text']='원래 OCR';self.assertEqual(self.intake([row])['status'],'VALIDATED_NOT_APPROVED')
 def test_timezone_and_invalid_timestamps(self):
  for stamp in ['2026-11-04T10:00:00','invalid',123]:
   with self.subTest(stamp=stamp):self.assertEqual(self.intake([{**self.row,'updated_at':stamp}])['status'],'HELD_INVALID_INPUT')
 def test_unknown_fields_and_semantic_flags_are_rejected(self):
  for row in [{**self.row,'approved':True},{**self.row,'semantic_verified':True},{**self.row,'status':'approved'},{**self.row,'source_checked':'true'}]:self.assertEqual(self.intake([row])['status'],'HELD_INVALID_INPUT')
 def test_backup_format_and_wrong_packet(self):
  p=self.dir/'backup.json';p.write_text(json.dumps({'schema':'cheongju-ocr-review-backup/1','packet_sha256':self.snapshot['packet_sha256'],'records':[self.row]}));self.assertEqual(v.parse_rows(p,self.snapshot['packet_sha256'],1),[self.row])
  with self.assertRaises(ValueError):v.parse_rows(p,'wrong',1)
 def test_invalid_packet_or_empty_file_does_not_count_reviews(self):
  r=v.intake(self.dir/'absent.html',root=self.dir);self.assertEqual(r['status'],'HELD_INVALID_PACKET');self.assertEqual(r['declared_checked_transcriptions'],0);self.assertEqual(self.intake([])['status'],'HELD_INVALID_INPUT')
 def test_invalid_report_cannot_replace_previous_result(self):
  p=self.dir/'result.json';p.write_text('previous valid result')
  with self.assertRaises(ValueError):v.save_report({'status':'HELD_INVALID_INPUT'},p)
  self.assertEqual(p.read_text(),'previous valid result')
 @unittest.skipUnless(shutil.which('node'),'Node interoperability')
 def test_browser_core_export_matches_backend_contract(self):
  r=self.snapshot['records']['item'];script="const c=require(process.argv[1]);const data=JSON.parse(require('fs').readFileSync(0,'utf8'));let x=c.blank(data.r,data.hash);x=c.edit(x,'reviewer','synthetic tester');x=c.edit(x,'source_checked',true);x=c.mark(x,'checked_transcription',data.r,data.hash);process.stdout.write(JSON.stringify(x));"
  result=subprocess.run(['node','-e',script,str(ROOT/'web/ocr_review_core.js')],input=json.dumps({'r':r,'hash':self.snapshot['packet_sha256']}),capture_output=True,text=True,check=True);row=json.loads(result.stdout);self.assertEqual(v.validate_row(row,self.snapshot)['status'],'checked_transcription')
if __name__=='__main__':unittest.main()
