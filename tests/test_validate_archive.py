import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import validate_archive as v

class ArchiveValidationTests(unittest.TestCase):
    def test_empty_foundation_passes(self):
        with tempfile.TemporaryDirectory() as d:
            result=v.validate(Path(d))
            self.assertEqual(result["status"],"PASS")

    def test_rejects_analysis_fields(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=root/"archive/people"; p.mkdir(parents=True)
            (p/"people.json").write_text(json.dumps([{
                "person_id":"p1","name":"홍길동","q_code":"Q01"
            }],ensure_ascii=False),encoding="utf-8")
            with self.assertRaises(SystemExit):
                v.validate(root)

    def test_rejects_duplicate_people(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=root/"archive/people"; p.mkdir(parents=True)
            rows=[{"person_id":"p1","name":"가"},{"person_id":"p1","name":"나"}]
            (p/"people.json").write_text(json.dumps(rows,ensure_ascii=False),encoding="utf-8")
            with self.assertRaises(SystemExit):
                v.validate(root)

if __name__=="__main__":
    unittest.main()
