"""No-network checks for official six-provisional targeted status comparison."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import probe_six_provisional_official_states_macos as p

class SixProvisionalTargetedStatusTests(unittest.TestCase):
    def test_only_explicit_leaf_status_y_n_is_verified(self):
        saved={
            "4018":{"publication_status":"provisional"},
            "4019":{"publication_status":"provisional"},
        }
        result=p.compare(saved,[
            {"var12":"4018","var09":"Y","text":"본회의 개회식"},
            {"var12":"4019","var09":"N","text":"본회의 제1호"},
        ],p.TARGET,"106","A010")
        self.assertEqual(result["records"]["4018"]["live_status"],"published")
        self.assertTrue(result["records"]["4018"]["status_changed"])
        self.assertEqual(result["records"]["4019"]["live_status"],"provisional")
        self.assertFalse(result["records"]["4019"]["status_changed"])
        self.assertEqual(result["leaf_count"],2)

    def test_missing_node_never_claims_deleted(self):
        saved={
            "4018":{"publication_status":"provisional"},
            "4019":{"publication_status":"provisional"},
        }
        x=p.compare(saved,[],p.TARGET,"106","A010")
        self.assertEqual(x["records"]["4018"]["verification"],
                         "NOT_LISTED_IN_TARGETED_OFFICIAL_COMMITTEE_BRANCH")
        self.assertIsNone(x["records"]["4018"]["live_status"])
        self.assertNotIn("status_changed",x["records"]["4018"])

    def test_unrecognized_official_status_is_not_assumed_provisional(self):
        saved={
            "4018":{"publication_status":"provisional"},
            "4019":{"publication_status":"provisional"},
        }
        x=p.compare(saved,[{"var12":"4019","var09":"?","text":"unexpected"}],
                    p.TARGET,"106","A010")
        self.assertEqual(x["records"]["4019"]["verification"],"UNKNOWN_OFFICIAL_STATUS_CODE")
        self.assertIsNone(x["records"]["4019"]["live_status"])
        self.assertIsNone(x["records"]["4019"]["status_changed"])

if __name__=="__main__":
    unittest.main()
