import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import link_bill_proposers as l

class BillProposerLinkTests(unittest.TestCase):
    def _write(self,path,obj):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")

    def test_exact_term_resolution(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self._write(root/"archive/people/people.json",[{"person_id":"p4","name":"홍길동"}])
            self._write(root/"archive/people/tenures.json",[{
                "person_id":"p4","council_scope":"cheongju_integrated","term":4
            }])
            idx=l.build_term_name_index(root)
            self.assertEqual(l.resolve_name(idx,4,"홍길동")["person_id"],"p4")
            self.assertEqual(l.resolve_name(idx,3,"홍길동")["status"],"unresolved")

    def test_same_term_duplicate_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self._write(root/"archive/people/history/cheongju_integrated_people.json",[
                {"person_id":"a","name":"홍길동"},{"person_id":"b","name":"홍길동"}
            ])
            self._write(root/"archive/people/history/cheongju_integrated_tenures.json",[
                {"person_id":"a","council_scope":"cheongju_integrated","term":2},
                {"person_id":"b","council_scope":"cheongju_integrated","term":2},
            ])
            idx=l.build_term_name_index(root)
            self.assertEqual(l.resolve_name(idx,2,"홍길동")["status"],"ambiguous_same_term")

    def test_link_preserves_roles(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self._write(root/"archive/people/people.json",[
                {"person_id":"p1","name":"홍길동"},{"person_id":"p2","name":"김철수"}
            ])
            self._write(root/"archive/people/tenures.json",[
                {"person_id":"p1","council_scope":"cheongju_integrated","term":4},
                {"person_id":"p2","council_scope":"cheongju_integrated","term":4},
            ])
            self._write(root/"archive/bills/items.json",[{
                "internal_number":"1","bill_number":"10","title":"시험안","term":4,
                "official_url":"https://example.invalid/bill",
                "representative_proposers":["홍길동"],"co_proposers":["김철수"],
                "full_proposer_names":["홍길동","김철수"]
            }])
            report=l.link(root)
            rows=json.loads((root/"archive/bills/proposer_memberships.json").read_text(encoding="utf-8"))
            roles={r["person_name"]:r["proposer_role"] for r in rows}
            self.assertEqual(roles["홍길동"],"representative")
            self.assertEqual(roles["김철수"],"co_proposer")
            self.assertEqual(report["resolved_exact_term"],2)

if __name__=="__main__":
    unittest.main()
