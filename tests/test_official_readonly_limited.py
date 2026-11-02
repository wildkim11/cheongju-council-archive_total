"""Zero-network tests for the strict three-call official source read-only probe."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import probe_official_readonly_limited as p


class OfficialLimitedProbeTests(unittest.TestCase):
    def test_post_must_be_root_read_only_query(self):
        for target,params in (
            (p.TREE,{"var10":"AnyOtherCommand"}),
            ("/minutes/svc/web/cms/mnts/SvcMntsViewer.php",{"var10":"SvcMntsTreeGnrtn"}),
            ("/untrusted",{"var10":"SvcMntsTreeGnrtn"}),
        ):
            with self.assertRaises(ValueError):
                p.official_request("POST",target,params)

    def test_get_must_use_known_official_viewer_path_and_numeric_source(self):
        for target in ("/",p.VIEWER,p.VIEWER+"?schSn=foo",
                       p.VIEWER+"?schSn=123&cmd=delete"):
            with self.assertRaises(ValueError):
                p.official_request("GET",target)

    def test_inconclusive_first_timeout_stops_no_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"report.json"
            fake=Mock(side_effect=TimeoutError("official read timeout"))
            result=p.probe(request_func=fake,output=path,sleep=lambda _:None)
            self.assertEqual(fake.call_count,1)
            self.assertEqual(result["requests_attempted"],1)
            self.assertEqual(result["requests_succeeded"],0)
            self.assertEqual(result["status"],"INCONCLUSIVE_SOURCE_UNAVAILABLE")
            self.assertEqual(len(result["errors"]),1)
            self.assertFalse(result["operational_release_authorized"])
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["requests_attempted"],1)

    def test_limited_live_root_and_two_viewers_use_only_three_calls(self):
        mock_tree=json.dumps([{"var01":str(i),"text":f"제{i}대"} for i in range(1,5)])
        raw_body="○위원장 홍길동\n"+"소규모 읽기전용 검증입니다. "*30
        fake_html=(
            "<!-- 회의록내용 -->"
            "<p>○위원장 홍길동</p><p>"
            +("소규모 읽기전용 검증입니다. "*30)
            +"</p><!--// 회의록내용 -->"
        )
        def fake(method,target,params):
            text=mock_tree if method=="POST" else fake_html
            return {
                "http_status":200,"response_bytes":len(text.encode("utf-8")),
                "response_sha256":hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text":text,
            }
        mocked=Mock(side_effect=fake)
        with tempfile.TemporaryDirectory() as folder:
            result=p.probe(request_func=mocked,output=Path(folder)/"report.json",sleep=lambda _:None)
            self.assertEqual(result["requests_attempted"],3)
            self.assertEqual(result["requests_succeeded"],3)
            self.assertEqual(result["successful_body_parses"],2)
            self.assertEqual(len(result["samples"]),2)
            self.assertTrue(result["tree_root"]["integrated_terms_1_to_4_present"])
            self.assertEqual(result["status"],"LIVE_RESPONDED_MANUAL_REVIEW_REQUIRED")
            self.assertFalse(result["operational_release_authorized"])
            self.assertFalse(result["source_archive_modified"])
            self.assertNotIn(raw_body,json.dumps(result,ensure_ascii=False))
            self.assertEqual(mocked.call_args_list[-1].args[0],"POST")
            self.assertEqual(mocked.call_args_list[-1].args[2],{"var10":"SvcMntsTreeGnrtn"})

    def test_body_comparison_matches_stored_sha_without_writing_body(self):
        body_text="○위원장 홍길동\n"+"회의록 원본 문자열 동일성 검사 내용입니다. "*25
        html=(
            "<!-- 회의록내용 -->"
            "<p>○위원장 홍길동</p><p>"
            +("회의록 원본 문자열 동일성 검사 내용입니다. "*25)
            +"</p><!--// 회의록내용 -->"
        )
        canonical=p.c.canonical(p.c.extract_minutes_body(html))
        hashvalue=hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        row={"source_id":"3999","date":"2026-09-09","term":4,
             "publication_status":"published","content_sha256":hashvalue}
        response={"http_status":200,"response_bytes":len(html),
                  "response_sha256":"d"*64,"text":html}
        result=p.compare_viewer(row,response)
        self.assertEqual(result["comparison"],"SAME_SAVED_BODY")
        self.assertEqual(result["live_body_sha256"],hashvalue)
        self.assertNotIn(body_text,json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    unittest.main()
