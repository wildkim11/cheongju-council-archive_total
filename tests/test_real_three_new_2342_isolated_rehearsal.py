"""No-network regression tests for exactly three real new official IDs in a 2342-copy rehearsal."""
from __future__ import annotations
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import rehearse_real_three_new_2342_full_copy_macos as q

class ThreeOfficialSourceFullCopySafetyTests(unittest.TestCase):
    def setUp(self):
        self.source=q.load(q.INDEX)
        self.assertEqual(len(self.source),2339)

    def test_confirmed_current_year_and_term_crosscheck_three_new_ids(self):
        rows, added, qa=q.build_verified_fixture(self.source)
        saved_ids={r["source_id"] for r in self.source}
        self.assertEqual(len(rows),2342)
        self.assertEqual(set(added),{"4024","4025","4026"})
        self.assertTrue(set(added).isdisjoint(saved_ids))
        self.assertTrue(all(r["term"]==4 for r in added.values()))
        self.assertTrue(all(r["publication_status"]=="provisional" for r in added.values()))
        self.assertTrue(all(r["inventory_sources"]==["term","year"] for r in added.values()))
        self.assertEqual(qa["term_inventory_count"],2342)
        self.assertEqual(qa["year_inventory_count"],2329)
        self.assertEqual(qa["only_year"],[])
        self.assertEqual(sum(r["publication_status"]=="provisional" for r in rows),9)
        self.assertEqual(sum(r["term"]==4 for r in rows),53)

    def test_4026_wrong_body_hash_fails_closed(self):
        monitor=q.load(q.PREVIOUS_BODY)
        for r in monitor["body_results"]:
            if r["source_id"]=="4026":
                r["current_body_sha256"]="0"*64
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"bad-proof.json"
            file.write_text(json.dumps(monitor),encoding="utf-8")
            with patch.object(q,"PREVIOUS_BODY",file):
                with self.assertRaisesRegex(ValueError,"PRIOR_NEW_BODY_HASH_BASELINE_MISMATCH"):
                    q.build_verified_fixture(self.source)

    def test_4026_absent_from_official_year2026_fails_closed(self):
        year=q.load(q.YEAR)
        year["found"].pop("4026")
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"bad-year.json"
            file.write_text(json.dumps(year),encoding="utf-8")
            with patch.object(q,"YEAR",file):
                with self.assertRaisesRegex(ValueError,"YEAR_2026_SOURCE_MEMBERSHIP_NOT_VERIFIED"):
                    q.build_verified_fixture(self.source)

    def test_official_year_status_not_provisional_is_not_guessed(self):
        year=q.load(q.YEAR)
        year["found"]["4026"]["official_status_code"]="Y"
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"bad-year.json"
            file.write_text(json.dumps(year),encoding="utf-8")
            with patch.object(q,"YEAR",file):
                with self.assertRaisesRegex(ValueError,"YEAR_2026_SOURCE_MEMBERSHIP_NOT_VERIFIED"):
                    q.build_verified_fixture(self.source)

    def test_new_source_id_collision_or_unexpected_4027_is_blocked(self):
        monitor=q.load(q.DISCOVERY)
        monitor["new_ids"][0]["source_id"]="4027"
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"bad-list.json"
            file.write_text(json.dumps(monitor),encoding="utf-8")
            with patch.object(q,"DISCOVERY",file):
                with self.assertRaisesRegex(ValueError,"UNEXPECTED_NEW_OFFICIAL_SOURCE_ID_SET"):
                    q.build_verified_fixture(self.source)

    def test_incomplete_current_official_list_is_rejected(self):
        monitor=q.load(q.DISCOVERY)
        monitor["official_term4_coverage_complete"]=False
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/"bad-list.json"
            file.write_text(json.dumps(monitor),encoding="utf-8")
            with patch.object(q,"DISCOVERY",file):
                with self.assertRaisesRegex(ValueError,"MONITOR_OFFICIAL_53_INVENTORY_NOT_COMPLETE_OR_STABLE"):
                    q.build_verified_fixture(self.source)

    def test_production_archive_root_still_hard_locked(self):
        with patch.object(q.platform,"system",return_value="Linux"):
            with self.assertRaisesRegex(RuntimeError,"MACOS_LIVE_REHEARSAL_ONLY"):
                q.run()
        with patch.object(q.c,"read_official_inventory",
                          side_effect=AssertionError("NO_OFFICIAL_NET_ALLOWED")):
            with self.assertRaisesRegex(RuntimeError,"LIVE_ARCHIVE_INCREMENTAL_SYNC_DISABLED"):
                q.c.run_sync("incremental",q.ROOT)

if __name__=="__main__":
    unittest.main()
