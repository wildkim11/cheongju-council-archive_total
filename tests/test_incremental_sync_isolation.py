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
        self.assertEqual(len(result["scenarios"]),6)
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
    def test_live_code_does_not_archive_same_id_revisions(self):
        result=qa.scenario_same_id_body_revision()
        self.assertTrue(result["same_path_overwritten"])
        self.assertTrue(result["old_bytes_not_preserved_in_history"])
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
        self.assertTrue(result["partial_publication_mutated_destination"])
        self.assertTrue(result["canonical_index_unchanged"])

if __name__=="__main__":
    unittest.main()
