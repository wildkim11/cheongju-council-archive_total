"""Regression tests for term-versus-year official tree discrepancy audit."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_official_tree_discrepancy import classify, offline, IDS

class TreeExceptionTests(unittest.TestCase):
    def test_dates_are_derived_from_official_session_title(self):
        x={"source_id":"180","term":1,"title":"제1대 의회(2014. 07. 01 ~ 2018. 06. 30 : 제001회 ~ 제034회) 제6회[임시회](2015. 01. 15 ~ 2015. 01. 17) 의회운영위원회 제1차(2015.01.23 금요일)",
           "date":"2015-01-23","publication_status":"published","official_url":"example"}
        a=classify(x)
        self.assertTrue(a["post_session"])
        self.assertEqual(a["session_end"],"2015-01-17")
        self.assertEqual(a["days_after_session_end"],6)
    def test_snapshot_exact_13_and_no_source_mutation(self):
        report=offline()
        self.assertEqual(report["total_saved"],2339)
        self.assertEqual(report["saved_term_only"],13)
        self.assertEqual({x["source_id"] for x in report["term_only"]},set(IDS))
        self.assertTrue(all(x["post_session"] and x["days_after_session_end"]>0
                            for x in report["term_only"]))
    def test_reject_title_without_session(self):
        with self.assertRaises(ValueError):
            classify({"source_id":"x","title":"unqualified meeting","date":"2025-01-01"})

if __name__=="__main__":
    unittest.main()
