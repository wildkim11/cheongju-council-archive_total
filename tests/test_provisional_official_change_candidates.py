"""No-network official provisional status change candidate evaluation tests."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import evaluate_provisional_official_changes as ev

def saved_rows():
    return [{"source_id":sid,"publication_status":"provisional",
             "sha256":sid*16,"path":f"archive/meetings/cheongju_integrated/term-4/2026/minutes-{sid}.md"}
            for sid in ev.EXPECTED]

def live_rows():
    return {
        "target_source_ids":list(ev.EXPECTED),
        "status":"PASS_ALL_SIX_OFFICIAL_STATUS_VERIFIED",
        "results_by_id":{
            sid:{"verification":"CONFIRMED_LIVE_OFFICIAL_LEAF","live_status":"provisional"}
            for sid in ev.EXPECTED
        },
    }

class CandidateEvaluationTests(unittest.TestCase):
    def test_no_changes_means_no_auto_publishing(self):
        r=ev.evaluate(saved_rows(),live_rows())
        self.assertEqual(r["decision"],"NO_CONFIRMED_STATUS_CHANGE_IN_SIX_PROVISIONAL_SOURCES")
        self.assertEqual(len(r["verified_unchanged"]),6)
        self.assertEqual(r["review_candidates"],[])
        self.assertFalse(r["production_update_authorized"])
        self.assertFalse(r["source_archive_modified"])
        self.assertFalse(r["full_official_inventory_verified"])

    def test_synthetic_one_becomes_published_is_review_only(self):
        actual=live_rows()
        actual["results_by_id"]["4019"]["live_status"]="published"
        r=ev.evaluate(saved_rows(),actual)
        self.assertEqual(r["decision"],"LIVE_STATUS_CHANGE_CANDIDATES_REQUIRING_BODY_VERIFICATION")
        self.assertEqual(len(r["review_candidates"]),1)
        self.assertEqual(r["review_candidates"][0]["source_id"],"4019")
        self.assertFalse(r["review_candidates"][0]["auto_apply"])
        self.assertEqual(len(r["verified_unchanged"]),5)

    def test_missing_official_leaf_fails_closed_and_is_not_deletion(self):
        actual=live_rows()
        del actual["results_by_id"]["4018"]
        r=ev.evaluate(saved_rows(),actual)
        self.assertEqual(r["decision"],"INCOMPLETE_SIX_ID_OFFICIAL_OBSERVATION")
        self.assertEqual(len(r["unverified"]),1)
        self.assertIn("NO_AUTO_DELETION",r["unverified"][0]["action"])

    def test_unsupported_or_extra_target_set_rejected(self):
        actual=live_rows()
        actual["target_source_ids"]=["4017"]
        with self.assertRaisesRegex(ValueError,"target changed"):
            ev.evaluate(saved_rows(),actual)

if __name__=="__main__":
    unittest.main()
