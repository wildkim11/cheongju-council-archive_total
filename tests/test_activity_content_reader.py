import shutil,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from install_activity_content import install,BOOT,START
class ActivityContentTests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('node'),'Node required')
 def test_reader_integrity_and_attribution(self):
  r=subprocess.run(['node',str(ROOT/'tests/activity_content_reader.cjs')],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_embedded_data_preserved_and_reinstall_idempotent(self):
  payload='<script id="release-bundle">{"x":"old"}</script>'
  a=install(payload+'window.__currentEvidence={}'+BOOT,'reader');self.assertIn(payload,a);self.assertEqual(install(a,'reader'),a)
 def test_unknown_or_broken_template_rejected(self):
  for html in [BOOT,'window.__currentEvidence={}'+BOOT+BOOT,'window.__currentEvidence={}'+START+BOOT]:
   with self.assertRaises(ValueError):install(html,'reader')
 def test_html_terminator_rejected(self):
  with self.assertRaises(ValueError):install('window.__currentEvidence={}'+BOOT,'</script>')
if __name__=='__main__':unittest.main()
