import json,subprocess,unittest
from pathlib import Path
class MeetingTextUpdateTests(unittest.TestCase):
 def test_validated_snapshot_update_contract(self):
  root=Path(__file__).resolve().parents[1]
  r=subprocess.run(['node',str(root/'tests/meeting_text_updates.test.cjs')],cwd=root,text=True,capture_output=True,timeout=30)
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertEqual(json.loads(r.stdout),{'status':'PASS','cases':10})
