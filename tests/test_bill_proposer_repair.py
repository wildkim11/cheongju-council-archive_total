import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import repair_bill_proposer_rosters as r

class BillProposerRepairTests(unittest.TestCase):
    def test_cut_stops_before_followup_fields(self):
        text="홍길동, 김철수 위원회 회부일 2026-01-01 상정일 2026-01-02"
        self.assertEqual(r._cut(text,["위원회 회부일","상정일"]),"홍길동,김철수")

    def test_match_names_uses_term_roster_only(self):
        seg="홍길동김철수위원회회부일가짜이름"
        self.assertEqual(r._match_names(seg,["홍길동","김철수"]),["홍길동","김철수"])

    def _write(self,path,obj):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")

    def test_nonmember_names_are_cleared_and_member_names_recovered(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self._write(root/"archive/people/people.json",[
                {"person_id":"p1","name":"홍길동"},{"person_id":"p2","name":"김철수"}
            ])
            self._write(root/"archive/people/tenures.json",[
                {"person_id":"p1","council_scope":"cheongju_integrated","term":4},
                {"person_id":"p2","council_scope":"cheongju_integrated","term":4},
            ])
            self._write(root/"archive/bills/items.json",[
                {
                    "internal_number":"1","term":4,"proposer_type_list":"시장",
                    "proposer_type":"시장","representative_proposers":["상정일"],
                    "co_proposers":["처리일"],"full_proposer_names":["상정일","처리일"]
                },
                {
                    "internal_number":"2","term":4,"proposer_type_list":"의원",
                    "proposer_type":"의원","representative_proposer_text":"홍길동 공동발의 김철수",
                    "co_proposers_text":"김철수 위원회 회부일 2026-01-01 처리결과 원안가결",
                    "full_proposer_names":["홍길동","김철수","상정일"]
                }
            ])
            report=r.repair(root)
            rows=json.loads((root/"archive/bills/items.json").read_text(encoding="utf-8"))
            self.assertEqual(rows[0]["full_proposer_names"],[])
            self.assertEqual(rows[1]["representative_proposers"],["홍길동"])
            self.assertEqual(rows[1]["co_proposers"],["김철수"])
            self.assertTrue(report["acceptance"]["nonmember_person_names_zero"])

if __name__=="__main__":
    unittest.main()
