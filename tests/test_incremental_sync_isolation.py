"""The current incremental collector is NOT production-certified.

These tests intentionally assert that fault-injected risk cases remain visible.
A green run proves that the diagnostic faithfully detects failure modes, not
that actual incremental collection is safe to enable.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import audit_incremental_sync_isolation as qa

class IsolationAuditTests(unittest.TestCase):
    def test_real_repository_sync_is_blocked_before_network(self):
        with patch.object(qa.c,"read_official_inventory",side_effect=AssertionError("network may not run")):
            with self.assertRaisesRegex(RuntimeError,"LIVE_ARCHIVE_INCREMENTAL_SYNC_DISABLED"):
                qa.c.run_sync("incremental",qa.ROOT)
            with self.assertRaisesRegex(RuntimeError,"LIVE_ARCHIVE_INCREMENTAL_SYNC_DISABLED"):
                qa.c.run_sync("full",qa.ROOT)

    def test_fixture_isolation_and_release_gate(self):
        result=qa.diagnose()
        self.assertEqual(result["official_site_requests"],0)
        self.assertFalse(result["canonical_project_files_modified"])
        self.assertEqual(len(result["scenarios"]),7)
        self.assertTrue(result["successes"]["real_repository_sync_hard_interlock"])
        self.assertTrue(result["successes"]["caught_publish_exception_restores_full_fixture"])
        self.assertTrue(result["successes"]["same_id_metadata_and_original_bytes_fail_closed"])
        self.assertEqual(result["release_blocker_count"],4)
        self.assertTrue(result["successes"]["new_markdown_appended_without_editing_old_source"])
        self.assertTrue(result["successes"]["remote_fetch_failure_aborts_without_writes"])
        self.assertEqual(result["release_decision"],"BLOCKED_UNSAFE_TO_OPERATE")
        self.assertGreater(result["release_blocker_count"],0)
    def test_diagnostic_exposes_stale_derived_views(self):
        result=qa.scenario_add_and_derived()
        self.assertTrue(result["added_new_source"])
        self.assertTrue(result["original_markdown_unchanged"])
        self.assertTrue(result["derived_meetings_export_stale"])
        self.assertTrue(result["term_shard_stale"])
    def test_same_id_metadata_transition_fails_closed(self):
        result=qa.scenario_same_id_status_transition()
        self.assertTrue(result["same_id_transition_safely_rejected"])
        self.assertTrue(result["fixture_unchanged"])
    def test_same_id_body_revision_fails_closed(self):
        result=qa.scenario_same_id_body_revision()
        self.assertTrue(result["same_id_body_revision_safely_rejected"])
        self.assertTrue(result["original_bytes_preserved"])
    def test_detect_many_to_one_safeguard_gap(self):
        result=qa.scenario_colliding_replacements()
        self.assertTrue(result["many_to_one_rejected"])
        self.assertIn("many-to-one",result["rejection_reason"])
    def test_simulated_network_failure_preserves_source(self):
        result=qa.scenario_fetch_failure()
        self.assertTrue(result["fixture_unchanged"])
    def test_simulated_publish_failure_is_detected(self):
        result=qa.scenario_publish_copy_failure()
        self.assertTrue(result["error_propagated"])
        self.assertTrue(result["fault_was_injected"])
        self.assertTrue(result["rollback_restored_destination"])
        self.assertFalse(result["new_markdown_exists_after_rollback"])
        self.assertTrue(result["canonical_index_unchanged"])

if __name__=="__main__":
    unittest.main()
