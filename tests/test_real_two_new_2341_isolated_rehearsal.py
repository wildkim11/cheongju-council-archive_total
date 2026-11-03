"""No-network regression tests for two-real-new isolated full copy fixture guards."""
from __future__ import annotations

from historical_snapshot import initial_meetings
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import rehearse_real_two_new_2341_full_copy_macos as q


class RealTwoNewSnapshotFixtureTests(unittest.TestCase):
    def setUp(self):
        self.source=initial_meetings()
        self.assertEqual(len(self.source),2339)

    def test_official_double_sourced_new_metadata_yields_only_two_new(self):
        rows,added,qa=q.build_verified_fixture(self.source)
        old_ids={r["source_id"] for r in self.source}
        self.assertEqual(len(rows),2341)
        self.assertEqual(set(added),{"4024","4025"})
        self.assertTrue(set(added).isdisjoint(old_ids))
        self.assertEqual(qa["term_inventory_count"],2341)
        self.assertEqual(qa["year_inventory_count"],2328)
        self.assertEqual(qa["only_year"],[])
        self.assertEqual(sum(r["publication_status"]=="provisional" for r in rows),8)
        self.assertEqual(sum(r["term"]==4 for r in rows),52)
        self.assertEqual(set(q.EXPECTED),{r["source_id"] for r in rows if r["source_id"] not in old_ids})
        self.assertTrue(all(r["inventory_sources"]==["term","year"] for r in added.values()))

    def test_wrong_new_body_sha_blocks_rehearsal(self):
        source=q.load(q.PREVIOUS_BODY)
        source["responses"][0]["body_normalized_sha256"]="0"*64
        with tempfile.TemporaryDirectory() as tmp:
            bad=Path(tmp)/"modified-proof.json"
            bad.write_text(json.dumps(source),encoding="utf-8")
            with patch.object(q,"PREVIOUS_BODY",bad):
                with self.assertRaisesRegex(ValueError,"PRIOR_NEW_BODY_HASH_BASELINE_MISMATCH"):
                    q.build_verified_fixture(self.source)

    def test_changed_official_source_id_set_fails_closed(self):
        source=q.load(q.DISCOVERY)
        source["new_source_id_candidates"][0]["source_id"]="4999"
        with tempfile.TemporaryDirectory() as tmp:
            bad=Path(tmp)/"bad-inventory.json"
            bad.write_text(json.dumps(source),encoding="utf-8")
            with patch.object(q,"DISCOVERY",bad):
                with self.assertRaisesRegex(ValueError,"UNEXPECTED_NEW_OFFICIAL_SOURCE_ID_SET"):
                    q.build_verified_fixture(self.source)

    def test_root_publication_requires_macos_never_runs_on_ubuntu(self):
        with patch.object(q.platform,"system",return_value="Linux"):
            with self.assertRaisesRegex(RuntimeError,"MACOS_LIVE_REHEARSAL_ONLY"):
                q.run()


if __name__=="__main__":
    unittest.main()
