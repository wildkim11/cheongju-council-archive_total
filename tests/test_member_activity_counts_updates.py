import subprocess,json,unittest
from pathlib import Path
class CountsUpdateTests(unittest.TestCase):
 def test_counts_update_integrity_identity_and_hold_contract(self):
  root=Path(__file__).resolve().parents[1]
  p=subprocess.run(['node',str(root/'tests/member_activity_counts_updates.test.cjs')],cwd=root,text=True,capture_output=True,timeout=30)
  self.assertEqual(p.returncode,0,p.stderr)
  self.assertEqual(json.loads(p.stdout),{'status':'PASS','cases':12})
