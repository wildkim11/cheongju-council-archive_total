import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from install_html_data_versions import install,START,END,BOOT
class HTMLVersionInstallTests(unittest.TestCase):
 def test_data_payload_is_preserved(self):
  payload='<script id="release-bundle" type="application/json">{"source":"historical","events":[1,2]}</script>';result=install(payload+BOOT,'function dataVersionsPanel(){}');self.assertIn(payload,result);self.assertLess(result.index(START),result.index(BOOT))
 def test_reinstall_is_idempotent(self):
  once=install(BOOT,'code');self.assertEqual(install(once,'code'),once);new=install(once,'replacement');self.assertEqual(new.count(START),1);self.assertIn('replacement',new)
 def test_duplicate_startup_fails_without_guessing(self):
  with self.assertRaises(ValueError):install(BOOT+BOOT,'code')
 def test_corrupt_marker_fails_closed(self):
  with self.assertRaises(ValueError):install(START+BOOT,'code')
if __name__=='__main__':unittest.main()
