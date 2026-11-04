import json,shutil,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from install_attachment_view import install,BOOT,START
D={'schema':'cheongju-attachment-view/1','commit':'a'*40,'manifest_sha256':'b'*64}
class AttachmentViewTests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('node'),'Node required')
 def test_reader_integrity_and_page_provenance(self):
  r=subprocess.run(['node',str(ROOT/'tests/attachment_text_reader.cjs')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_payload_preservation_and_reinstall(self):
  original='<script id="release-bundle" type="application/json">{"historical":true}</script>window.__activityContent={}'+BOOT
  result=install(original,'reader',D);self.assertIn('{"historical":true}',result);self.assertEqual(result,install(result,'reader',D));self.assertEqual(result.count('id="attachment-text-view"'),1)
 def test_corrupt_or_duplicate_module_fails(self):
  for s in [BOOT,'window.__activityContent={}'+START+BOOT,'window.__activityContent={}'+BOOT+BOOT]:
   with self.assertRaises(ValueError):install(s,'reader',D)
 def test_invalid_descriptor_and_script_terminator(self):
  s='<script id="release-bundle">{}</script>window.__activityContent={}'+BOOT
  with self.assertRaises(ValueError):install(s,'reader',{**D,'commit':'main'})
  with self.assertRaises(ValueError):install(s,'</script>',D)
 def test_escaped_legacy_template_is_not_a_second_release_tag(self):
  actual='<script id="release-bundle" type="application/json">{"historical":true}</script>'
  escaped='<script id="release-bundle" type="application\\/json">'
  result=install(actual+escaped+'window.__activityContent={}'+BOOT,'reader',D)
  self.assertEqual(result.count('id="attachment-text-view"'),1);self.assertIn(actual,result);self.assertIn(escaped,result)
if __name__=='__main__':unittest.main()
