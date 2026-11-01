import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_remaining_bill_sources as a

class PendingBillAuditTests(unittest.TestCase):
    def test_exception_ids_have_no_overlap(self):
        self.assertEqual(len(set(a.REMAINING)), 8)
        self.assertEqual(len(set(a.INSTITUTIONAL)), 5)
        self.assertFalse(set(a.REMAINING) & set(a.INSTITUTIONAL))
    def test_snapshot_is_not_mutated_and_counts(self):
        result=a.summarize()
        self.assertEqual(result["pending_member_bill_count"],8)
        self.assertEqual(result["institutional_bill_anomaly_count"],5)
        self.assertEqual(result["institutional_person_relationships"],44)
        self.assertEqual(result["data_writes_to_canonical_archive"],0)
        self.assertTrue(all(x["existing_person_link_count"]==0 for x in result["member_bills"]))
        self.assertTrue(all(x["relationship_names_equal_bill_roster"] for x in result["institutional_anomalies"]))
if __name__=="__main__":
    unittest.main()
