"""No-network tests for stable official monitoring failure/change alert grouping."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import prepare_official_operations_alert as a

def good_term4():
    return {
        "status":"PASS_REVIEW_CANDIDATES_PRESENT",
        "new_ids":[{"source_id":"4024"},{"source_id":"4025"},{"source_id":"4026"}],
        "status_change_candidates":[],
        "metadata_change_candidates":[],
        "body_change_candidates":[],
    }

def good_history():
    return {
        "status":"PASS_SCOPED_NO_CHANGES_OBSERVED",
        "new_id_candidates":[],
        "metadata_or_status_candidates":[],
        "cross_term_id_candidates":[],
    }

class OfficialOperationsAlertTests(unittest.TestCase):
    def test_real_new_three_create_deduplicated_candidate_fingerprint(self):
        x=a.classify(good_term4(),good_history(),"success")
        y=a.classify(good_term4(),good_history(),"success")
        self.assertEqual(x["kind"],"review")
        self.assertEqual(x["fingerprint"],y["fingerprint"])
        self.assertEqual(x["candidates"]["new_source_ids"],["4024","4025","4026"])
        self.assertFalse(x["notification_delivery_confirmed"])
        self.assertTrue(x["no_archive_changes"])

    def test_no_changes_does_not_issue_alert(self):
        t=good_term4()
        t["new_ids"]=[]
        x=a.classify(t,good_history(),"success")
        self.assertEqual(x["kind"],"none")

    def test_failure_always_outweighs_candidates(self):
        h=good_history()
        h["status"]="BLOCKED_INCOMPLETE_OFFICIAL_HISTORIC_SESSION_INSPECTION"
        x=a.classify(good_term4(),h,"failure")
        self.assertEqual(x["kind"],"error")
        self.assertNotEqual(x["fingerprint"],a.classify(good_term4(),good_history(),"success")["fingerprint"])

    def test_report_absent_on_checkout_or_runner_failure_still_generates_error(self):
        self.assertEqual(a.classify(None,None,"failure")["kind"],"error")
        self.assertEqual(a.classify(None,None,"success")["kind"],"error")

    def test_durable_output_contains_no_original_body(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            term4=folder/"term4.json"
            historic=folder/"historic.json"
            term4.write_text(json.dumps(good_term4()),encoding="utf-8")
            historic.write_text(json.dumps(good_history()),encoding="utf-8")
            output=folder/"alert.json"
            body=folder/"body.md"
            result=a.prepare(output=output,body_path=body,
                   term4_path=term4,history_path=historic,
                   run_url="https://github.com/example/repo/actions/runs/101",
                   job_result="success")
            self.assertEqual(result["kind"],"review")
            self.assertTrue(output.exists() and body.exists())
            self.assertIn("FINGERPRINT=",body.read_text())
            self.assertIn("4026",body.read_text())
            self.assertNotIn("원문 내용",body.read_text())

if __name__=="__main__":
    unittest.main()
