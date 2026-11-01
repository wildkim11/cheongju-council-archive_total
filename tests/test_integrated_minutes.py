import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_integrated_minutes as c


class IntegratedMinutesTests(unittest.TestCase):
    def test_meeting_type(self):
        self.assertEqual(c._meeting_type("본회의 제1차", None), "plenary")
        self.assertEqual(
            c._meeting_type("예산결산특별위원회 제1차", "C999"),
            "budget_special_committee",
        )
        self.assertEqual(
            c._meeting_type("행정사무감사 제1일", "C201"),
            "administrative_audit",
        )

    def test_extract_minutes_body(self):
        html = (
            "<!-- 회의록내용 -->"
            "<p>○위원장 홍길동</p><p>"
            + "시설 점검을 요청합니다. " * 20
            + "</p><!--// 회의록내용 -->"
        )
        text = c.extract_minutes_body(html)
        self.assertIn("홍길동", text)

    def test_term_is_from_official_root_not_date(self):
        roots = [
            {"var01": str(n), "text": f"제{n}대", "var10": "x"} for n in range(1, 5)
        ]

        def fake_tree(kind, node):
            if node.get("var10") == "SvcMntsTreeGnrtn":
                return roots
            term = int(node["var01"])
            # deliberately use the same date for every term; official root must win.
            return [
                {
                    "text": "본회의 제1차(2024.01.01 월요일)",
                    "var12": str(1000 + term),
                    "var09": "Y",
                    "var02": "C100",
                }
            ]

        with patch.object(c, "_tree", side_effect=fake_tree):
            rows = c.inventory_by_term("2026-11-01")

        self.assertEqual([r["term"] for r in rows], [1, 2, 3, 4])
        self.assertTrue(all(r["council_scope"] == "cheongju_integrated" for r in rows))

    def test_write_record_has_scope_and_version_state(self):
        row = {
            "meeting_id": "cheongju_integrated:minutes-1",
            "legacy_minutes_id": "minutes-1",
            "council_scope": "cheongju_integrated",
            "term": 1,
            "title": "시험 회의",
            "date": "2014-07-01",
            "year": 2014,
            "committee_code": "C101",
            "meeting_type": "committee",
            "publication_status": "provisional",
            "official_url": c.BASE + "/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=1",
            "source_id": "1",
        }
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = c.write_record(root, row, "○위원 홍길동\n" + "질문입니다. " * 30, "2026-11-01T00:00:00+09:00")
            self.assertEqual(result["publication_status"], "provisional")
            self.assertTrue((root / result["path"]).exists())


if __name__ == "__main__":
    unittest.main()
