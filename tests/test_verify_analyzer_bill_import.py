"""Hermetic, no-network checks for the downstream bill proposer import boundary."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_analyzer_bill_import import (
    UnsafeBillImport, load_verified_personal_proposers,
    RAW, SAFE, QUARANTINE,
)


class SafeAnalyzerBillImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "exports/analyzer"
        self.out.mkdir(parents=True)
        self.bills = [
            {"internal_number": "1", "proposer_type_list": "의원", "proposer_type": "의원"},
            {"internal_number": "2", "proposer_type_list": "시장", "proposer_type": "시장"},
            {"internal_number": "3", "proposer_type_list": "의원", "proposer_type": "시장"},
            {"internal_number": "4", "proposer_type_list": "의원"},
        ]
        self.links = [
            {"internal_number": str(i), "person_name": "동명이인", "source_url": "https://example.test/" + str(i)}
            for i in range(1, 5)
        ]
        self._write_all()

    def _write_all(self):
        datasets = {}
        data = {
            "bills": self.bills,
            RAW: self.links,
            SAFE: [self.links[0], self.links[3]],
            QUARANTINE: [self.links[1], self.links[2]],
        }
        for name, rows in data.items():
            path = self.out / (name + ".jsonl")
            blob = ("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                            for row in rows)).encode("utf-8")
            path.write_bytes(blob)
            datasets[name] = {"path": "exports/analyzer/" + name + ".jsonl",
                              "rows": len(rows), "sha256": hashlib.sha256(blob).hexdigest()}
        self.manifest = {
            "schema": "cheongju-council-archive-analyzer-export/0.1",
            "datasets": datasets,
            "principles": {
                "source_facts_only": True,
                "analysis_judgments_included": False,
                "personal_proposer_statistics_dataset": SAFE,
                "institutional_type_person_names_quarantined_dataset": QUARANTINE,
            },
        }
        self._save_manifest()

    def _save_manifest(self):
        (self.out / "manifest.json").write_text(
            json.dumps(self.manifest, ensure_ascii=False), encoding="utf-8"
        )

    def test_verified_view_keeps_only_personal_and_preserves_original(self):
        original = {x.name: x.read_bytes() for x in self.out.iterdir()}
        rows, report = load_verified_personal_proposers(self.root)
        self.assertEqual([x["internal_number"] for x in rows], ["1", "4"])
        self.assertEqual(report["raw_links"], 4)
        self.assertEqual(report["quarantined_links"], 2)
        self.assertFalse(report["external_analyzer_connection_verified"])
        self.assertEqual(original, {x.name: x.read_bytes() for x in self.out.iterdir()})

    def test_missing_safe_file_never_falls_back_to_raw(self):
        (self.out / (SAFE + ".jsonl")).unlink()
        with self.assertRaises(UnsafeBillImport):
            load_verified_personal_proposers(self.root)

    def test_legacy_raw_dataset_cannot_be_declared_personal(self):
        self.manifest["principles"]["personal_proposer_statistics_dataset"] = RAW
        self._save_manifest()
        with self.assertRaises(UnsafeBillImport):
            load_verified_personal_proposers(self.root)

    def test_bad_sha_fails_closed(self):
        path = self.out / (SAFE + ".jsonl")
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(UnsafeBillImport, "SHA-256 mismatch"):
            load_verified_personal_proposers(self.root)

    def test_wrong_partition_fails_even_with_matching_new_sha(self):
        name = SAFE
        path = self.out / (name + ".jsonl")
        rows = [self.links[0], self.links[2], self.links[3]]
        blob = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows).encode("utf-8")
        path.write_bytes(blob)
        self.manifest["datasets"][name]["sha256"] = hashlib.sha256(blob).hexdigest()
        self.manifest["datasets"][name]["rows"] = len(rows)
        self._save_manifest()
        with self.assertRaisesRegex(UnsafeBillImport, "misclassified"):
            load_verified_personal_proposers(self.root)

    def test_unknown_person_link_fails_closed(self):
        self.links[0]["internal_number"] = "999"
        self._write_all()
        with self.assertRaisesRegex(UnsafeBillImport, "unknown bill"):
            load_verified_personal_proposers(self.root)

    def test_manifest_path_cannot_be_redirected(self):
        self.manifest["datasets"][SAFE]["path"] = "exports/analyzer/" + RAW + ".jsonl"
        self._save_manifest()
        with self.assertRaisesRegex(UnsafeBillImport, "Unexpected dataset path"):
            load_verified_personal_proposers(self.root)


if __name__ == "__main__":
    unittest.main()
