import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import build_identity_candidates as b

class IdentityCandidateTests(unittest.TestCase):
    def _write(self,path,obj):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")

    def test_same_name_is_candidate_not_merge(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self._write(root/"archive/people/people.json",[{"person_id":"p1","name":"홍길동"}])
            self._write(root/"archive/people/history/cheongju_integrated_people.json",[{"person_id":"p2","name":"홍길동"}])
            report=b.build(root)
            self.assertEqual(report["automatic_merges"],0)
            rows=json.loads((root/"archive/people/identity_candidates.json").read_text(encoding="utf-8"))
            self.assertTrue(any(r["candidate_type"]=="same_normalized_name" for r in rows))

if __name__=="__main__":
    unittest.main()
