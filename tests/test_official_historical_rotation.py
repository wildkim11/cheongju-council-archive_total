"""No-network tests for historical term 1-3 bounded rolling official metadata."""
from __future__ import annotations
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import monitor_official_historical_rotation_macos as h

DAY=dt.date(2026,11,2)

def fake_tree(node):
    name=node.get("var11")
    if node.get("var10")=="SvcMntsTreeGnrtn":
        return [{"var01":str(term),"var03":"","var11":f"sessions-{term}",
                 "text":f"제{term}대"} for term in (1,2,3,4)]
    if name in ("sessions-1","sessions-2","sessions-3"):
        term=name.split("-")[1]
        return [{"var01":term,"var03":str(ses),
                 "var11":f"committees-{term}-{ses}","text":f"제{ses}회"}
                for ses in (10,11)]
    if name and name.startswith("committees-"):
        _,term,ses=name.split("-")
        return [{"var01":term,"var03":ses,"var02":"A010",
                 "var11":f"leaves-{term}-{ses}","text":"본회의"}]
    if name and name.startswith("leaves-"):
        _,term,ses=name.split("-")
        sid=str(900000+int(term)*1000+int(ses))
        return [{"var12":sid,"var09":"Y",
                 "text":"제1호(2026.10.12 월요일)"}]
    raise AssertionError("Unexpected tree payload "+repr(node))

class HistoricalRotationTests(unittest.TestCase):
    def test_daily_rotation_is_per_term_and_deterministic(self):
        rows=[{"var01":"1","var03":str(ses)} for ses in (10,11,12)]
        a,index=h.select_session(rows,1,DAY)
        b,next_index=h.select_session(rows,1,DAY+dt.timedelta(days=1))
        self.assertEqual(a["var03"],"10")
        self.assertEqual(index,0)
        self.assertEqual(b["var03"],"11")
        self.assertEqual(next_index,1)
        self.assertEqual(h.select_session(rows,1,DAY+dt.timedelta(days=3))[0]["var03"],"10")

    def test_session_bad_or_duplicate_number_blocks(self):
        with self.assertRaisesRegex(ValueError,"invalid or repeated"):
            h.select_session([
                {"var01":"2","var03":"20"},
                {"var01":"2","var03":"20"},
            ],2,DAY)
        with self.assertRaisesRegex(ValueError,"wrong term"):
            h.select_session([{"var01":"3","var03":"21"}],1,DAY)

    def test_current_scope_three_complete_sessions_with_three_new_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"report.json"
            with patch.object(h.platform,"system",return_value="Darwin"):
                x=h.scan(read=fake_tree,pause=lambda _:None,day=DAY,out=out)
            self.assertEqual(x["status"],"PASS_SCOPED_REVIEW_CANDIDATES_PRESENT")
            self.assertEqual(x["requests_attempted"],10) # root, 3 term roots, 3 session, 3 leaf
            self.assertTrue(x["all_three_selected_sessions_complete"])
            self.assertEqual(len(x["new_id_candidates"]),3)
            self.assertEqual(len(x["selected_session_branches"]),3)
            self.assertEqual([r["selected_session_number"] for r in x["selected_session_branches"]],["10"]*3)
            self.assertEqual([r["full_term_cycle_days_if_daily_success"] for r in x["selected_session_branches"]],[2]*3)
            self.assertFalse(x["any_missing_saved_id_inferred"])
            self.assertEqual(x["whole_terms_completely_scanned"],[])
            self.assertFalse(x["production_archive_modified"])
            self.assertTrue(out.exists())

    def test_broken_committee_tree_fails_closed_and_does_not_infer_deletion(self):
        def broken(node):
            if str(node.get("var11","")).startswith("leaves-2-"):
                raise TimeoutError("simulated official source timed out")
            return fake_tree(node)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(h.platform,"system",return_value="Darwin"):
                x=h.scan(read=broken,pause=lambda _:None,day=DAY,
                         out=Path(tmp)/"report.json")
            self.assertEqual(x["status"],"BLOCKED_INCOMPLETE_OFFICIAL_HISTORIC_SESSION_INSPECTION")
            self.assertFalse(x["all_three_selected_sessions_complete"])
            self.assertEqual(x["branch_errors"][0]["type"],"TimeoutError")
            self.assertFalse(x["any_missing_saved_id_inferred"])
            self.assertEqual(x["whole_terms_completely_scanned"],[])

    def test_same_official_source_id_in_two_leaves_blocks(self):
        def duplicate(node):
            if node.get("var11")=="leaves-1-10":
                sample=fake_tree(node)[0]
                return [sample,sample]
            return fake_tree(node)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(h.platform,"system",return_value="Darwin"):
                x=h.scan(read=duplicate,pause=lambda _:None,day=DAY,
                         out=Path(tmp)/"result.json")
            self.assertTrue(x["status"].startswith("BLOCKED_"))
            self.assertIn("Duplicate",x["branch_errors"][0]["reason"])

    def test_known_stored_status_change_is_review_only(self):
        sample=json.loads((h.ROOT/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
        first=next(x for x in sample if x["term"]==1)
        changed={
            "source_id":first["source_id"],
            "title":first["title"],
            "date":first["date"],
            "committee_code":first["committee_code"],
            "publication_status":"provisional" if first["publication_status"]=="published" else "published",
            "official_url":first["official_url"],
        }
        x=h.compare_branch(sample,[changed],1,"10")
        self.assertEqual(len(x["metadata_or_status_candidates"]),1)
        self.assertIn("publication_status",x["metadata_or_status_candidates"][0]["differences"])
        self.assertEqual(x["missing_saved_ids_claimed"],[])

    def test_unsupported_host_platform_cannot_use_official_network(self):
        with patch.object(h.platform,"system",return_value="Linux"):
            with self.assertRaisesRegex(RuntimeError,"MACOS"):
                h.scan(read=lambda _:self.fail("Unexpected real network"))

if __name__=="__main__":
    unittest.main()
