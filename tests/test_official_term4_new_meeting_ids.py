"""Entirely offline unit tests for bounded macOS term-4 official ID detection."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import probe_official_term4_new_meeting_ids_macos as q


def old(sid,term=4,status="published",title="old title",date="2026-10-12",committee="A010"):
    return {
        "source_id":str(sid),
        "term":term,
        "publication_status":status,
        "title":title,
        "date":date,
        "committee_code":committee,
        "official_url":q.OFFICIAL_BASE+str(sid),
        "sha256":"1"*64,
    }


def live(sid,status="published",title="old title",date="2026-10-12",committee="A010"):
    return {
        "source_id":str(sid),
        "publication_status":status,
        "title":title,
        "date":date,
        "committee_code":committee,
        "session":"106",
        "official_url":q.OFFICIAL_BASE+str(sid),
    }


class Term4NewIdClassifyTests(unittest.TestCase):
    def test_new_meeting_id_is_never_auto_applied(self):
        results=q.classify([old("4019",status="provisional"),old("3980",term=3)],
                           [live("4019",status="provisional"),live("4023")],True)
        self.assertEqual([r["source_id"] for r in results["new_source_id_candidates"]],["4023"])
        self.assertEqual(results["conclusion"],"TERM4_INVENTORY_HAS_REVIEW_CANDIDATES")
        self.assertFalse(results["new_source_id_candidates"][0]["auto_apply"])
        self.assertFalse(results["existing_source_files_modified"])
        self.assertFalse(results["production_archive_update_allowed"])

    def test_status_and_metadata_changes_are_review_only(self):
        r=q.classify([old("4019",status="provisional")],
                     [live("4019",status="published",date="2026-10-13")],True)
        self.assertEqual(len(r["status_change_candidates"]),1)
        self.assertEqual(len(r["metadata_change_candidates"]),1)
        self.assertFalse(r["status_change_candidates"][0]["auto_apply"])

    def test_partial_discovery_never_implies_deletion(self):
        r=q.classify([old("4019")],[],False)
        self.assertFalse(r["official_term4_coverage_complete"])
        self.assertEqual(r["missing_saved_term4_ids_full_branch_only"],[])
        self.assertEqual(r["conclusion"],"INCONCLUSIVE_PARTIAL_OFFICIAL_TERM4_INVENTORY")

    def test_full_missing_meeting_never_claims_deleted(self):
        r=q.classify([old("4019")],[],True)
        self.assertEqual(r["missing_saved_term4_ids_full_branch_only"],["4019"])
        self.assertFalse(r["production_archive_update_allowed"])

    def test_duplicate_official_id_forces_inconclusive(self):
        r=q.classify([old("4019")],[live("4019"),live("4019")],True)
        self.assertEqual(r["conclusion"],"INCONCLUSIVE_PARTIAL_OFFICIAL_TERM4_INVENTORY")
        self.assertTrue(r["unknown_or_duplicate_issues"])

    def test_same_id_other_term_is_reclassification_not_new_id(self):
        r=q.classify([old("500",term=3)],[live("500")],True)
        self.assertEqual(r["new_source_id_candidates"],[])
        self.assertEqual(r["observed_in_other_term_saved_ids"][0]["source_id"],"500")

    def test_offline_root_session_committee_leaf_fixture_without_http(self):
        original=[old(str(i),term=1) for i in range(1,2290)]
        old_term=[old(str(i)) for i in range(5000,5050)]
        archived=original+old_term
        self.assertEqual(len(archived),2339)

        def offline_tree(payload):
            fn=payload.get("var11")
            if payload.get("var10")=="SvcMntsTreeGnrtn":
                return [{"var01":"1","var03":"","text":"제1대"},
                        {"var01":"4","var03":"","var11":"SvcMntsTreeGnrtnSesn","text":"제4대 의회"}]
            if fn=="SvcMntsTreeGnrtnSesn":
                return [{"var01":"4","var03":"106","var11":"SvcMntsTreeGnrtnCmmtNm",
                         "text":"제106회[정례회]"}]
            if fn=="SvcMntsTreeGnrtnCmmtNm":
                return [{"var01":"4","var03":"106","var02":"A010",
                         "var11":"SvcMntsTreeGnrtnChasu","text":"본회의"}]
            if fn=="SvcMntsTreeGnrtnChasu":
                return [{"var12":"5050","var09":"N","text":"제1호(2026.10.12 월요일)"}]
            self.fail("Unexpected or unauthorized tree fetch "+repr(payload))
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"baseline.json"
            output=Path(td)/"result.json"
            source.write_text(json.dumps(archived),encoding="utf-8")
            with patch.object(q,"INDEX",source),patch.object(q.platform,"system",return_value="Darwin"):
                report=q.discover(read=offline_tree,sleep=lambda _:None,out=output)
            self.assertEqual(report["requests_attempted"],4)
            self.assertTrue(report["all_term4_session_branches_exhausted"])
            self.assertEqual(len(report["new_source_id_candidates"]),1)
            self.assertEqual(report["new_source_id_candidates"][0]["source_id"],"5050")
            self.assertEqual(len(report["missing_saved_term4_ids_full_branch_only"]),50)
            self.assertFalse(report["production_sync_enabled"])
            self.assertEqual(json.loads(output.read_text())["request_limit"],80)

    def test_non_leaf_or_bad_status_leaves_collection_inconclusive(self):
        old_full=[old(str(i),term=1) for i in range(1,2290)]+[old(str(i)) for i in range(5000,5050)]
        def fake(payload):
            fn=payload.get("var11")
            if payload.get("var10")=="SvcMntsTreeGnrtn":
                return [{"var01":"4","var03":"","var11":"SvcMntsTreeGnrtnSesn","text":"제4대 의회"}]
            if fn=="SvcMntsTreeGnrtnSesn":
                return [{"var01":"4","var03":"106","var11":"SvcMntsTreeGnrtnCmmtNm","text":"제106회"}]
            if fn=="SvcMntsTreeGnrtnCmmtNm":
                return [{"var01":"4","var02":"A010","var03":"106",
                         "var11":"SvcMntsTreeGnrtnChasu","text":"본회의"}]
            return [{"var12":"","var09":"","text":"unexpected nested branch"}]
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"saved.json"
            source.write_text(json.dumps(old_full),encoding="utf-8")
            with patch.object(q,"INDEX",source),patch.object(q.platform,"system",return_value="Darwin"):
                r=q.discover(read=fake,sleep=lambda _:None,out=Path(td)/"out.json")
            self.assertEqual(r["conclusion"],"INCONCLUSIVE_PARTIAL_OFFICIAL_TERM4_INVENTORY")
            self.assertTrue(r["branch_errors"])
            self.assertEqual(r["missing_saved_term4_ids_full_branch_only"],[])


if __name__=="__main__":
    unittest.main()
