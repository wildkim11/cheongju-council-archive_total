import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_stage_c as a


class StageCOfflineAuditTests(unittest.TestCase):
    def fixture(self, root):
        records = []
        now = "2026-11-02T01:54:49.271400+09:00"
        for term in (1, 2, 3, 4):
            sid = str(100 + term)
            date = f"{2014 + (term - 1) * 4}-07-01" if term < 4 else "2026-07-01"
            title = f"제{term}대 본회의"
            source = a.SOURCE_URL + sid
            body = "○위원장 홍길동  회의를 시작하겠습니다. " + ("이번 의사일정을 검토하겠습니다. " * 20)
            rendered_body = "## " + body
            markdown = (
                f"# {title}\n\n"
                f"- official_url: {source}\n"
                f"- meeting_date: {date}\n"
                f"- collected_at: {now}\n"
                f"- source_id: {sid}\n"
                f"- council_scope: {a.SCOPE}\n"
                f"- term: {term}\n"
                "- publication_status: published\n\n"
                f"{rendered_body}\n"
            )
            rel = f"archive/meetings/{a.SCOPE}/term-{term}/{date[:4]}/minutes-{sid}.md"
            self.write(root / rel, markdown)
            row = {
                "meeting_id": f"{a.SCOPE}:minutes-{sid}",
                "legacy_minutes_id": f"minutes-{sid}",
                "council_scope": a.SCOPE,
                "term": term,
                "title": title,
                "date": date,
                "year": int(date[:4]),
                "publication_status": "published",
                "source_id": sid,
                "official_url": source,
                "inventory_sources": ["term", "year"] if term < 4 else ["term"],
                "path": rel,
                "content_sha256": a.sha256(a.canon(body).encode()),
                "sha256": a.sha256(markdown.encode()),
                "bytes": len(markdown.encode()),
                "first_seen_at": now,
                "last_checked_at": now,
            }
            records.append(row)
            self.write_json(root / f"indexes/integrated/initial_term_{term}.json", [row])
            self.write_json(root / f"reports/integrated-initial-term-{term}.json", {"listed": 1})
        self.write_json(root / "indexes/integrated/meetings.json", records)
        self.write_json(root / "indexes/integrated/meeting_history.json", [])
        self.write_json(root / "reports/integrated-sync.json", {
            "listed": 4,
            "by_term": {str(n): 1 for n in range(1, 5)},
            "published": 4,
            "provisional": 0,
            "history_rows": 0,
            "inventory_qa": {
                "term_inventory_count": 4,
                "year_inventory_count": 3,
                "only_term": ["104"],
                "only_year": [],
            }
        })
        export = root / "exports/analyzer/meetings.jsonl"
        self.write(export, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records))
        self.write_json(root / "exports/analyzer/manifest.json", {
            "principles": {"source_facts_only": True},
            "datasets": {
                "meetings": {
                    "path": "exports/analyzer/meetings.jsonl",
                    "rows": 4,
                    "sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
                }
            },
        })
        return records

    @staticmethod
    def write(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_json(self, path, obj):
        self.write(path, json.dumps(obj, ensure_ascii=False, indent=2))

    def test_round_trip_all_invariants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            result = a.audit(root)
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["source_files_checked"], 4)
            self.assertEqual(result["sha256_content_verified"], 4)
            self.assertEqual(result["year_inventory_only_term"][0]["source_id"], "104")

    def test_tampered_markdown_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = self.fixture(root)
            file = root / records[0]["path"]
            file.write_bytes(file.read_bytes() + b"Tampering\n")
            result = a.audit(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any("SHA-256 mismatch" in x for x in result["errors"]))

    def test_export_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            file = root / "exports/analyzer/meetings.jsonl"
            file.write_bytes(file.read_bytes() + b'{"unexpected":true}\n')
            result = a.audit(root)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any("export" in x or "manifest" in x for x in result["errors"]))


if __name__ == "__main__":
    unittest.main()
