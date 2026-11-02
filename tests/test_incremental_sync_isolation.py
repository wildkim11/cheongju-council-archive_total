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
        self.assertEqual(len(result["scenarios"]),8)
        self.assertTrue(result["successes"]["real_repository_sync_hard_interlock"])
        self.assertTrue(result["successes"]["caught_publish_exception_restores_full_fixture"])
        self.assertTrue(result["successes"]["same_id_metadata_and_original_bytes_versioned"])
        self.assertEqual(result["release_blocker_count"],1)
        self.assertTrue(result["successes"]["staged_analyzer_exports_and_current_term_shards_are_consistent"])
        self.assertTrue(result["successes"]["new_markdown_appended_without_editing_old_source"])
        self.assertTrue(result["successes"]["remote_fetch_failure_aborts_without_writes"])
        self.assertEqual(result["release_decision"],"BLOCKED_UNSAFE_TO_OPERATE")
        self.assertGreater(result["release_blocker_count"],0)
    def test_staged_current_shards_and_exports_are_consistent(self):
        result=qa.scenario_add_and_derived()
        self.assertTrue(result["added_new_source"])
        self.assertTrue(result["original_markdown_unchanged"])
        self.assertTrue(result["derived_meetings_export_matches_current"])
        self.assertTrue(result["term_shard_matches_current"])
        self.assertTrue(result["initial_term_shard_preserved"])
        self.assertEqual(result["derived_manifest_meetings_count"],2)
    def test_same_id_metadata_transition_retains_original(self):
        result=qa.scenario_same_id_status_transition()
        self.assertTrue(result["same_id_transition_versioned"])
        self.assertTrue(result["prior_exact_original_bytes_preserved"])
        self.assertEqual(result["revision_rows"],1)
        self.assertEqual(result["prior_status"],"provisional")
        self.assertEqual(result["next_status"],"published")
    def test_same_id_body_revision_retains_original(self):
        result=qa.scenario_same_id_body_revision()
        self.assertTrue(result["content_revision_changed_current"])
        self.assertTrue(result["original_bytes_immutable"])
        self.assertTrue(result["prior_sha256_matches"])
        self.assertEqual(result["revision_rows"],1)
    def test_multiple_revisions_and_return_to_original_body(self):
        result=qa.scenario_revert_after_revisions()
        self.assertTrue(result["three_transitions_recorded"])
        self.assertTrue(result["all_old_bytes_still_present"])
        self.assertTrue(result["original_first_version_preserved"])

    def test_same_id_date_change_within_year_retains_previous_source(self):
        import tempfile
        import json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            old=qa.row(916,date="2026-10-01")
            before_record=qa.fixture(root,[old])[0]
            before_bytes=(root/before_record["path"]).read_bytes()
            changed=qa.row(916,date="2026-10-02",
                           title="제4대 제107회 본회의 제1차(2026.10.02 금요일)")
            qa.sync(root,[changed])
            current=json.loads((root/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))[0]
            ledger=json.loads((root/"indexes/integrated/meeting_revisions.json").read_text(encoding="utf-8"))
            self.assertEqual(current["date"],"2026-10-02")
            self.assertEqual(len(ledger),1)
            self.assertEqual((root/ledger[0]["revision_path"]).read_bytes(),before_bytes)
            self.assertIn("- meeting_date: 2026-10-02",
                          (root/current["path"]).read_text(encoding="utf-8"))

    def test_cross_year_same_id_migration_keeps_prior_in_immutable_revision(self):
        import tempfile,json,hashlib
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            old=qa.row(915,date="2025-12-30")
            old["term"]=3
            original=qa.fixture(root,[old])[0]
            original_path=root/original["path"]
            original_bytes=original_path.read_bytes()
            moved=qa.row(915,date="2026-01-02",
                         title="제4대 제107회 본회의 제1차(2026.01.02 금요일)")
            report=qa.sync(root,[moved])
            current=json.loads((root/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))[0]
            revisions=json.loads((root/"indexes/integrated/meeting_revisions.json").read_text(encoding="utf-8"))
            self.assertEqual(len(revisions),1)
            self.assertEqual(current["term"],4)
            self.assertEqual(current["date"],"2026-01-02")
            self.assertEqual(current["path"],"archive/meetings/cheongju_integrated/term-4/2026/minutes-915.md")
            self.assertFalse(original_path.exists(),"obsolete canonical path must be absent after migration")
            self.assertEqual((root/revisions[0]["revision_path"]).read_bytes(),original_bytes)
            self.assertEqual(revisions[0]["prior_sha256"],hashlib.sha256(original_bytes).hexdigest())
            self.assertEqual(report["migrated_old_paths"],[original["path"]])
            self.assertIn("term-3/2025",revisions[0]["prior_path"])
            self.assertTrue((root/current["path"]).is_file())
            self.assertEqual(len(json.loads((root/"indexes/integrated/current_term_3.json").read_text(encoding="utf-8"))),0)
            self.assertEqual(len(json.loads((root/"indexes/integrated/current_term_4.json").read_text(encoding="utf-8"))),1)

    def test_cross_year_same_term_migration(self):
        import tempfile,json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            old=qa.row(917,date="2025-12-29")
            prior=qa.fixture(root,[old])[0]
            prior_bytes=(root/prior["path"]).read_bytes()
            changed=qa.row(917,date="2026-01-04",
                         title="제4대 제107회 본회의 제1차(2026.01.04 일요일)")
            qa.sync(root,[changed])
            ledger=json.loads((root/"indexes/integrated/meeting_revisions.json").read_text(encoding="utf-8"))
            self.assertEqual(len(ledger),1)
            self.assertFalse((root/prior["path"]).exists())
            self.assertEqual((root/ledger[0]["revision_path"]).read_bytes(),prior_bytes)
            self.assertTrue((root/"archive/meetings/cheongju_integrated/term-4/2026/minutes-917.md").exists())

    def test_cross_year_migration_source_fetch_failure_preserves_original(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            old=qa.row(918,date="2025-12-29")
            qa.fixture(root,[old])
            before=qa.snapshot(root)
            changed=qa.row(918,date="2026-01-04")
            with patch.object(qa.c,"read_official_inventory",return_value=([changed],{"only_term":[],"only_year":[]})), \
                 patch.object(qa.c,"fetch",side_effect=TimeoutError("offline injected timeout")):
                with self.assertRaisesRegex(RuntimeError,"Failed meeting"):
                    qa.c.run_sync("incremental",root)
            self.assertEqual(qa.snapshot(root),before)

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
