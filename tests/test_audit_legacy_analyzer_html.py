"""No-network regression tests of existing analyzer HTML audit (no migration)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_legacy_analyzer_html import AnalyzerPreflightError, inspect_html


class AuditLegacyAnalyzerHTMLTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "example.html"
        self.data = {
            "meta": {"schema": "cheongju-integrated-html-embedded-data/1.0", "generated_at": "2026-09-27"},
            "facts": [{"fact_id": "f-1", "domain": "BILLS", "source_ref": {"source_item_id": "bills-opaque-1"},
                       "title": "동일한 제목", "council_scope": "cheongju-integrated"},
                      {"fact_id": "f-2", "domain": "SPEECH", "source_ref": {"source_item_id": "speech-opaque-2"}}],
            "member_fact_links": [{"fact_id": "f-1", "member_id": "member-1", "member_name": "가나다"}],
        }
        self._write()

    def _write(self):
        self.path.write_text('<html><script id="cca-data" type="application/json">' +
                             json.dumps(self.data, ensure_ascii=False) + '</script></html>', encoding="utf-8")

    def test_no_name_or_title_crosswalk_even_if_structural_valid(self):
        initial = self.path.read_bytes()
        report = inspect_html(self.path)
        self.assertEqual(report["status"], "STRUCTURAL_PASS_CROSSWALK_NOT_VERIFIED")
        self.assertEqual(report["normalized_bill_fact_count"], 1)
        self.assertEqual(report["bill_member_fact_links_count"], 1)
        self.assertFalse(report["official_archive_join_authorized"])
        self.assertEqual(self.path.read_bytes(), initial)

    def test_orphan_link_fails(self):
        self.data["member_fact_links"][0]["fact_id"] = "missing"
        self._write()
        with self.assertRaisesRegex(AnalyzerPreflightError, "Orphan"):
            inspect_html(self.path)

    def test_duplicate_fact_id_fails(self):
        self.data["facts"].append(dict(self.data["facts"][0]))
        self._write()
        with self.assertRaisesRegex(AnalyzerPreflightError, "duplicate"):
            inspect_html(self.path)

    def test_proposer_roles_alone_do_not_authorize_join(self):
        self.data["facts"][0].update({"internal_number": "999", "proposer_type": "의원"})
        self.data["member_fact_links"][0]["proposer_role"] = "representative"
        self._write()
        self.assertFalse(inspect_html(self.path)["official_archive_join_authorized"])

    def test_invalid_schema_fails(self):
        self.data["meta"]["schema"] = "unknown"
        self._write()
        with self.assertRaisesRegex(AnalyzerPreflightError, "schema"):
            inspect_html(self.path)

    def test_suspect_archive_manifest_does_not_authorize_raw(self):
        manifest = Path(self.tmp.name) / "manifest.json"
        manifest.write_text(json.dumps({"schema": "cheongju-council-archive-analyzer-export/0.1",
                                        "principles": {"personal_proposer_statistics_dataset": "bill_proposers"},
                                        "datasets": {}}), encoding="utf-8")
        with self.assertRaisesRegex(AnalyzerPreflightError, "Invalid external archive manifest"):
            inspect_html(self.path, manifest)


if __name__ == "__main__":
    unittest.main()
