"""No-network release-interlock regression for explicit published body rechecks."""
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_integrated_minutes as c


class ForcePublishedBodyRecheckGuard(unittest.TestCase):
    def test_real_root_never_unlocked_by_forced_body_ids(self):
        with patch.object(c,"read_official_inventory",
                          side_effect=AssertionError("MUST_NOT_READ_NETWORK")):
            with self.assertRaisesRegex(RuntimeError,"LIVE_ARCHIVE_INCREMENTAL_SYNC_DISABLED"):
                c.run_sync("incremental",c.ROOT,
                           force_body_ids={"cheongju_integrated:minutes-3999"})

    def test_unknown_forced_body_id_blocks_before_any_archive_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"disposable-only"
            root.mkdir()
            with patch.object(c,"read_official_inventory",return_value=([],{})):
                with self.assertRaisesRegex(ValueError,"FORCED_BODY_REVIEW_ID_NOT_IN_SAVED_INDEX"):
                    c.run_sync("incremental",root,
                               force_body_ids={"cheongju_integrated:minutes-99999999"})
            self.assertFalse((root/"indexes/integrated/meetings.json").exists())

if __name__=="__main__":
    unittest.main()
