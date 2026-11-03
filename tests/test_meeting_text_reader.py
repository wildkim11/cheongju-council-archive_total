"""Run the dependency-free browser text reader's integrity regression cases."""
import json,subprocess,unittest
from pathlib import Path
class MeetingTextReaderTests(unittest.TestCase):
 def test_browser_text_reader_integrity_and_rejection_cases(self):
  root=Path(__file__).resolve().parents[1]
  result=subprocess.run(['node',str(root/'tests/meeting_text_reader.test.cjs')],cwd=root,text=True,capture_output=True,timeout=30)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(json.loads(result.stdout),{'status':'PASS','cases':10})
