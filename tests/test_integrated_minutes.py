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

    def test_merge_official_inventories_uses_term_as_authority(self):
        term = [{
            "source_id": "10",
            "meeting_id": "cheongju_integrated:minutes-10",
            "legacy_minutes_id": "minutes-10",
            "council_scope": "cheongju_integrated",
            "term": 2,
            "title": "제2대 본회의",
            "date": "2020-01-01",
            "year": 2020,
            "committee_code": "C100",
            "meeting_type": "plenary",
            "publication_status": "published",
            "official_url": c.BASE + "/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=10",
        }]
        year = [{
            "source_id": "10",
            "title": "2020년 본회의",
            "date": "2020-01-01",
            "year": 2020,
            "committee_code": "C100",
            "meeting_type": "plenary",
            "publication_status": "published",
            "official_url": c.BASE + "/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=10",
        }]
        rows, qa = c.merge_official_inventories(term, year)
        self.assertEqual(rows[0]["term"], 2)
        self.assertEqual(rows[0]["inventory_sources"], ["term", "year"])
        self.assertEqual(qa["shared_count"], 1)

    def test_year_only_inventory_refuses_term_inference(self):
        term = []
        year = [{
            "source_id": "99",
            "title": "회의",
            "date": "2020-01-01",
            "year": 2020,
            "committee_code": "C100",
            "meeting_type": "committee",
            "publication_status": "published",
            "official_url": c.BASE + "/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=99",
        }]
        with self.assertRaises(ValueError):
            c.merge_official_inventories(term, year)

    def test_detect_provisional_replacement(self):
        old = [{
            "meeting_id": "cheongju_integrated:minutes-1",
            "publication_status": "provisional",
            "committee_code": "C101",
            "title": "제4대 제10회 본회의 제1차(2026.10.01 목요일)",
            "date": "2026-10-01",
        }]
        live = [{
            "meeting_id": "cheongju_integrated:minutes-2",
            "publication_status": "published",
            "committee_code": "C101",
            "title": "제4대 제10회 본회의 제1차(2026.10.02 금요일)",
            "date": "2026-10-02",
        }]
        self.assertEqual(
            c.detect_replacements(old, live),
            {"cheongju_integrated:minutes-1": "cheongju_integrated:minutes-2"},
        )

    def test_published_disappearance_is_hard_failure(self):
        old = [{
            "meeting_id": "cheongju_integrated:minutes-1",
            "publication_status": "published",
            "committee_code": "C101",
            "title": "제4대 본회의 제1차(2026.10.01)",
            "date": "2026-10-01",
        }]
        with self.assertRaises(ValueError):
            c.detect_replacements(old, [])


    def test_incremental_sync_preserves_superseded_provisional_history(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            old_id="cheongju_integrated:minutes-1"
            new_id="cheongju_integrated:minutes-2"
            old_path="archive/meetings/cheongju_integrated/term-4/2026/minutes-1.md"
            (root/Path(old_path).parent).mkdir(parents=True,exist_ok=True)
            (root/old_path).write_text("# old provisional\n",encoding="utf-8")
            (root/"indexes/integrated").mkdir(parents=True,exist_ok=True)
            old=[{
                "meeting_id":old_id,
                "legacy_minutes_id":"minutes-1",
                "council_scope":"cheongju_integrated",
                "term":4,
                "title":"제4대 제10회 본회의 제1차(2026.10.01 목요일)",
                "date":"2026-10-01",
                "year":2026,
                "committee_code":"C101",
                "meeting_type":"plenary",
                "publication_status":"provisional",
                "official_url":c.BASE+"/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=1",
                "source_id":"1",
                "path":old_path,
                "content_sha256":"oldhash",
                "sha256":"oldfilehash",
                "bytes":18,
                "first_seen_at":"2026-10-01T00:00:00+09:00",
                "last_checked_at":"2026-10-01T00:00:00+09:00",
                "supersedes":None,
                "superseded_by":None,
            }]
            old[0]=c.write_record(
                root,old[0],
                "○위원장 홍길동\n"+("기존 임시회의록 원문을 점검합니다. "*24),
                "2026-10-01T00:00:00+09:00"
            )
            (root/"indexes/integrated/meetings.json").write_text(
                json.dumps(old,ensure_ascii=False),encoding="utf-8"
            )
            live=[{
                "meeting_id":new_id,
                "legacy_minutes_id":"minutes-2",
                "council_scope":"cheongju_integrated",
                "term":4,
                "title":"제4대 제10회 본회의 제1차(2026.10.02 금요일)",
                "date":"2026-10-02",
                "year":2026,
                "committee_code":"C101",
                "meeting_type":"plenary",
                "publication_status":"published",
                "official_url":c.BASE+"/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=2",
                "source_id":"2",
                "inventory_sources":["term","year"],
            }]
            body_html=(
                "<!-- 회의록내용 --><p>○위원장 홍길동</p><p>"
                + "정식회의록 본문입니다. "*20
                + "</p><!--// 회의록내용 -->"
            )
            with patch.object(c,"read_official_inventory",return_value=(live,{"shared_count":1})), \
                 patch.object(c,"fetch",return_value=body_html):
                report=c.run_sync("incremental",root)

            current=json.loads((root/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
            history=json.loads((root/"indexes/integrated/meeting_history.json").read_text(encoding="utf-8"))
            self.assertEqual(current[0]["meeting_id"],new_id)
            self.assertEqual(current[0]["publication_status"],"published")
            self.assertEqual(current[0]["supersedes"],old_id)
            self.assertEqual(history[0]["meeting_id"],old_id)
            self.assertEqual(history[0]["publication_status"],"superseded")
            self.assertEqual(history[0]["superseded_by"],new_id)
            self.assertEqual(report["superseded"],{old_id:new_id})


    def test_initial_shard_complete_requires_exact_inventory_and_body_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            row={
                "meeting_id":"cheongju_integrated:minutes-10",
                "legacy_minutes_id":"minutes-10",
                "council_scope":"cheongju_integrated",
                "term":1,
                "title":"제1대 본회의",
                "date":"2014-07-01",
                "year":2014,
                "committee_code":"C100",
                "meeting_type":"plenary",
                "publication_status":"published",
                "official_url":c.BASE+"/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=10",
                "source_id":"10",
                "inventory_sources":["term","year"],
                "path":"archive/meetings/cheongju_integrated/term-1/2014/minutes-10.md",
                "content_sha256":"a"*64,
            }
            path=root/row["path"]
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("# body\n",encoding="utf-8")
            self.assertTrue(c._initial_shard_complete(root,[row],[row]))
            changed=[{**row,"publication_status":"provisional"}]
            self.assertFalse(c._initial_shard_complete(root,changed,[row]))

    def test_assemble_initial_requires_exact_four_term_coverage(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            live=[]
            dates={1:"2015-01-01",2:"2019-01-01",3:"2023-01-01",4:"2026-07-01"}
            for term in c.SUPPORTED_TERMS:
                row={
                    "meeting_id":f"cheongju_integrated:minutes-{term}",
                    "legacy_minutes_id":f"minutes-{term}",
                    "council_scope":"cheongju_integrated",
                    "term":term,
                    "title":f"제{term}대 본회의",
                    "date":dates[term],
                    "year":int(dates[term][:4]),
                    "committee_code":"C100",
                    "meeting_type":"plenary",
                    "publication_status":"published",
                    "official_url":c.BASE+f"/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn={term}",
                    "source_id":str(term),
                    "inventory_sources":["term","year"],
                    "path":f"archive/meetings/cheongju_integrated/term-{term}/{dates[term][:4]}/minutes-{term}.md",
                    "content_sha256":"b"*64,
                    "sha256":"c"*64,
                    "bytes":100,
                    "first_seen_at":"2026-11-02T00:00:00+09:00",
                    "last_checked_at":"2026-11-02T00:00:00+09:00",
                    "supersedes":None,
                    "superseded_by":None,
                }
                live.append(row)
                p=root/row["path"]
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text("# x\n",encoding="utf-8")
                sp=c._initial_shard_path(root,term)
                sp.parent.mkdir(parents=True,exist_ok=True)
                sp.write_text(json.dumps([row],ensure_ascii=False),encoding="utf-8")
            with patch.object(c,"read_official_inventory",return_value=(live,{"shared_count":4})):
                report=c.assemble_initial(root)
            self.assertEqual(report["listed"],4)
            current=json.loads((root/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
            self.assertEqual(len(current),4)

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
