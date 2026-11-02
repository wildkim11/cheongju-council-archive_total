import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from audit_stage_a_people_count import audit

class StageAPeopleCountTests(unittest.TestCase):
    def test_434_plus_one_is_435_not_distinct_person_count(self):
        report=audit(ROOT)
        self.assertEqual(report["status"],"PASS")
        self.assertEqual(report["previous_baseline_excluding_historical_only"],434)
        self.assertEqual(report["extra_historical_only"],1)
        self.assertEqual(report["archived_profile_records"],435)
        self.assertEqual(report["archived_tenure_records"],435)
        self.assertEqual(report["single_added_record"]["name"],"최영중")
        self.assertEqual(report["single_added_record"]["official_profile_code"],"4200")
        self.assertEqual(report["single_added_record"]["identity_status"],"candidate_unmerged")
        self.assertFalse(report["archive_data_modified"])
        self.assertIn("NOT 435 verified distinct natural persons",report["meaning"])

if __name__=="__main__":
    unittest.main()
