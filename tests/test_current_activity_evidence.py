import shutil,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from install_current_activity_evidence import install,BOOT,START
class CurrentEvidenceTests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('node'),'Node required')
 def test_projection_semantics(self):
  result=subprocess.run(['node',str(ROOT/'tests/current_activity_evidence.cjs')],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_install_keeps_all_payload_bytes_and_is_idempotent(self):
  payload='<script id="release-bundle">{"events":["historical"]}</script>'
  original=payload+'function dataVersionsPanel(){}'+BOOT
  one=install(original,'safe code');self.assertIn(payload,one);self.assertEqual(install(one,'safe code'),one)
 def test_invalid_template_and_incomplete_module_are_rejected(self):
  for html in [BOOT,BOOT+BOOT,'function dataVersionsPanel(){}'+START+BOOT]:
   with self.assertRaises(ValueError):install(html,'safe code')
 def test_script_termination_is_rejected(self):
  with self.assertRaises(ValueError):install('function dataVersionsPanel(){}'+BOOT,'</script>')
if __name__=='__main__':unittest.main()
