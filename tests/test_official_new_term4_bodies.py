"""Offline regressions for new official body hash checks; absolutely no network."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import probe_official_new_term4_bodies_macos as q


class TestTerm4NewBodyReadonly(unittest.TestCase):
    def setUp(self):
        self.src={
            "source_id":"4024",
            "official_url":"https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=4024",
            "official_date":"2026-10-14",
            "official_status":"provisional",
        }

    def test_offline_realistic_provisional_body_extracts_and_matches_hash(self):
        payload=(
            "<!-- 회의록내용 --><p>[본 회의록은 최종교정 전 임시회의록이므로 법적 효력이 없습니다]</p>"
            "<p>제106회 도시건설위원회 제1호(2026.10.14)</p>"
            "<p>"+("청주시의회 소위원회 공식 발언내용 원문 보존. "*15)+"</p>"
            "<!--// 회의록내용 -->"
        ).encode("utf-8")
        d=q.classify_body(self.src,200,payload)
        self.assertEqual(d["verification"],"BODY_EXTRACTED_OFFICIAL_NEW_ID")
        self.assertTrue(d["body_extracted"])
        self.assertEqual(d["response_sha256"],hashlib.sha256(payload).hexdigest())
        self.assertNotIn("청주시의회 소위원회",repr(d))

    def test_http_502_not_misreported_as_parsed_body(self):
        d=q.classify_body(self.src,502,b"upstream connect error")
        self.assertEqual(d["verification"],"NON_200_HTTP_INCONCLUSIVE")
        self.assertNotIn("body_normalized_sha256",d)

    def test_published_notices_absence_does_not_imply_parser_failed(self):
        src={**self.src,"official_status":"published"}
        payload=(
            "<!-- 회의록내용 --><p>정식 회의록 내용입니다. "+("위원장 발언 안건 처리. "*25)+"</p>"
            "<!--// 회의록내용 -->"
        ).encode("utf-8")
        d=q.classify_body(src,200,payload)
        self.assertEqual(d["verification"],"BODY_EXTRACTED_OFFICIAL_NEW_ID")

    def test_no_default_unauthorized_dynamic_source_id(self):
        with self.assertRaises(ValueError):
            q.get_viewer("9999")

if __name__=="__main__":
    unittest.main()
