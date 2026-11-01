import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from find_bill_minutes_fallback import compact
from reconcile_bill_proposers_from_minutes import parse_full_roster,search_minutes_for_bill
from link_bill_proposers import build_term_name_index
from promote_bill_1960_from_minutes import EXPECTED_NAMES,SOURCE_MEETING_ID

ROOT=Path(__file__).resolve().parents[1]
class VerifiedBill1960Tests(unittest.TestCase):
    def test_official_meeting_and_title_variant(self):
        all_meetings=json.loads((ROOT/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
        m=next(x for x in all_meetings if x["meeting_id"]==SOURCE_MEETING_ID)
        self.assertEqual(m["date"],"2021-10-19")
        self.assertEqual(m["term"],2)
        items=json.loads((ROOT/"archive/bills/items.json").read_text(encoding="utf-8"))
        bill=next(x for x in items if str(x["internal_number"])=="1960")
        self.assertEqual(bill.get("proposer_type_list"),"의원")
        self.assertEqual(bill["term"],2)
        raw=(ROOT/m["path"]).read_text(encoding="utf-8")
        self.assertIn("ㆍ",raw)
        self.assertIn("·",bill["title"])
        self.assertIn(compact(bill["title"]),compact(raw))
        ev=search_minutes_for_bill(
            {"term":2,"title":bill["title"],"session":bill["session"],
             "proposal_date":bill["proposal_date"],
             "processed_date":bill.get("processed_date_list") or "2021-10-22"},
            [m],ROOT,build_term_name_index(ROOT),{})
        self.assertTrue(ev)
        full=[x for x in ev if x["evidence_type"]=="complete_explicit_roster"]
        self.assertTrue(full)
        self.assertTrue(all(x["representative"]=="박노학" and set(x["all_names"])==EXPECTED_NAMES for x in full))
        self.assertTrue(all(x["every_name_unique_same_term"] for x in full))
    def test_reject_roster_without_explicit_proposer_ending(self):
        self.assertIsNone(parse_full_roster("(박노학 의원 대표발의)(박노학 외 12명)"))
if __name__=="__main__":
    unittest.main()
