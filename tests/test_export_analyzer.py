import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import export_analyzer as e

class AnalyzerExportTests(unittest.TestCase):
    def _write(self,path,obj):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")

    def test_export_creates_jsonl_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self._write(root/"archive/people/people.json",[{"person_id":"p1","name":"홍길동"}])
            self._write(root/"archive/people/tenures.json",[{"person_id":"p1","council_scope":"cheongju_integrated","term":4}])
            manifest=e.export(root)
            self.assertEqual(manifest["datasets"]["people"]["rows"],1)
            self.assertTrue((root/"exports/analyzer/people.jsonl").exists())
            self.assertTrue((root/"exports/analyzer/manifest.json").exists())

    def test_full_meetings_override_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self._write(root/"indexes/integrated/meeting_inventory.json",[{"meeting_id":"inventory"}])
            self._write(root/"indexes/integrated/meetings.json",[{"meeting_id":"full"}])
            manifest=e.export(root)
            self.assertEqual(manifest["datasets"]["meetings"]["rows"],1)
            text=(root/"exports/analyzer/meetings.jsonl").read_text(encoding="utf-8")
            self.assertIn('"full"',text)
            self.assertNotIn('"inventory"',text)

if __name__=="__main__":
    unittest.main()
