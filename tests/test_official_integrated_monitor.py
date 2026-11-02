"""No-network safety tests for the pre-production macOS official monitor."""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import audit_stage_c
import monitor_official_incremental_preflight as m


def saved():
    return json.loads((m.ROOT/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))


def discovered():
    return json.loads((m.ROOT/"reports/official-term4-new-meeting-id-discovery-20261102.json").read_text(encoding="utf-8"))


def official_html(body):
    return ("<!-- 회의록내용 -->"
            + "<p>"+html.escape(body)+"</p>"
            + "<!--// 회의록내용 -->").encode("utf-8")


class IntegratedOfficialMonitorTests(unittest.TestCase):
    def setUp(self):
        self.saved=saved()
        self.discovery=discovered()
        self.date=dt.date(2026,11,2)
        self.assertEqual(len(self.saved),2339)

    def test_bounded_plan_includes_six_provisional_two_new_and_rotating_published(self):
        plan=m.plan_body_reads(self.saved,self.discovery,self.date)
        self.assertEqual(plan["new_source_ids"],["4024","4025"])
        self.assertEqual(plan["old_provisional_ids"],["4017","4018","4019","4020","4021","4022"])
        self.assertEqual(len(plan["published_sample_ids"]),8)
        self.assertEqual(len(plan["ordered_ids"]),16)
        self.assertEqual(len(set(plan["ordered_ids"])),16)
        self.assertEqual(plan["body_request_cap"],20)

    def test_rotation_moves_and_wraps_without_persistent_cursor(self):
        p1=m.plan_body_reads(self.saved,self.discovery,self.date)
        p2=m.plan_body_reads(self.saved,self.discovery,dt.date(2026,11,3))
        self.assertNotEqual(p1["published_sample_ids"],p2["published_sample_ids"])
        p3=m.plan_body_reads(self.saved,self.discovery,self.date)
        self.assertEqual(p1["published_sample_ids"],p3["published_sample_ids"])

    def test_new_id_is_review_only(self):
        body="신규 회의록 임시 발언 내용입니다. "*15
        item=m.evaluate_official_body("4024",None,200,official_html(body),["new_source"])
        self.assertEqual(item["verification"],"NEW_OFFICIAL_BODY_READABLE_REVIEW_ONLY")
        self.assertIsNone(item["body_changed"])
        self.assertNotIn("본문",repr(item))
        self.assertEqual(item["current_body_sha256"],hashlib.sha256(
            m.original.canonical(body).encode("utf-8")
        ).hexdigest())

    def test_existing_changed_body_is_review_candidate_not_auto_write(self):
        body="내용이 변경된 공식 회의록입니다. "*18
        row={"content_sha256":"0"*64}
        item=m.evaluate_official_body("4019",row,200,official_html(body),
                                      ["saved_provisional"])
        self.assertEqual(item["verification"],"EXISTING_OFFICIAL_BODY_CHANGED_REVIEW_REQUIRED")
        self.assertTrue(item["body_changed"])
        summary=m.summarize([item],{"new_source_id_candidates":[],
            "status_change_candidates":[],"metadata_change_candidates":[]})
        self.assertTrue(summary["has_review_candidates"])
        self.assertEqual(len(summary["body_change_candidates"]),1)

    def test_existing_same_body_hash_is_unchanged(self):
        body="동일하게 보존된 원문 발언입니다. "*19
        expected=hashlib.sha256(m.original.canonical(body).encode("utf-8")).hexdigest()
        item=m.evaluate_official_body("4019",{"content_sha256":expected},200,
                                      official_html(body),["saved_provisional"])
        self.assertEqual(item["verification"],"EXISTING_OFFICIAL_BODY_UNCHANGED")
        self.assertFalse(item["body_changed"])

    def test_official_non200_status_is_unverified(self):
        item=m.evaluate_official_body("4019",{"content_sha256":"a"*64},
                                      503,b"upstream unavailable",["saved_provisional"])
        self.assertEqual(item["verification"],"HTTP_ERROR_NO_CONTENT_VERIFIED")
        self.assertNotIn("body_changed",item)

    def test_missing_official_leaf_is_a_blocker_not_deletion(self):
        incomplete={**self.discovery,"official_term4_coverage_complete":False}
        with self.assertRaisesRegex(ValueError,"INCOMPLETE"):
            m.plan_body_reads(self.saved,incomplete,self.date)
        missing={**self.discovery,"missing_saved_term4_ids_full_branch_only":["4019"]}
        with self.assertRaisesRegex(ValueError,"MISSING"):
            m.plan_body_reads(self.saved,missing,self.date)

    def test_excessive_new_ids_refused(self):
        info=dict(self.discovery)
        original=self.discovery["new_source_id_candidates"][0]
        info["new_source_id_candidates"]=[
            {**original,"source_id":str(5000+i),
             "official_url":m.original.BASE+m.VIEWER+str(5000+i)}
            for i in range(9)
        ]
        with self.assertRaisesRegex(ValueError,"EXCEED"):
            m.plan_body_reads(self.saved,info,self.date)

    def test_publication_transition_always_selected_even_if_not_sampled(self):
        result=dict(self.discovery)
        result["status_change_candidates"]=[{
            "source_id":"3999","stored_status":"published",
            "live_official_status":"provisional","auto_apply":False,
        }]
        plan=m.plan_body_reads(self.saved,result,self.date)
        self.assertIn("3999",plan["ordered_ids"])
        self.assertIn("status_change",plan["purposes"]["3999"])

    def test_monitor_offline_partial_inventory_fails_closed_without_viewer_get(self):
        def fake_tree(out):
            return {**self.discovery,"official_term4_coverage_complete":False,
                    "conclusion":"INCONCLUSIVE_PARTIAL_OFFICIAL_TERM4_INVENTORY",
                    "branch_errors":[{"error_type":"TimeoutError"}],
                    "requests_attempted":1}
        calls=[]
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/"monitor.json"
            with patch.object(m.platform,"system",return_value="Darwin"), \
                 patch.object(m.audit_stage_c,"audit",return_value={"status":"PASS"}):
                result=m.monitor(
                    read=lambda sid:calls.append(sid),
                    scan_date=self.date,output=output,
                    discover=fake_tree,pause=lambda x:None,
                )
            self.assertEqual(result["status"],"BLOCKED_INCONCLUSIVE_SOURCE_OR_BUDGET")
            self.assertEqual(result["actual_official_body_requests"],0)
            self.assertEqual(calls,[])
            self.assertFalse(result["archive_root_modified"])
            self.assertTrue(output.is_file())

    def test_current_baseline_full_monitor_mock_no_network(self):
        # Fake official HTML faithfully reconstructs each of the 14 existing
        # saved bodies; the two new source bodies are explicitly SYNTHETIC.
        lookup={str(row["source_id"]):row for row in self.saved}
        calls=[]
        def fake_read(sid):
            calls.append(sid)
            if sid in lookup:
                row=lookup[sid]
                _,_,body=audit_stage_c.markdown_parts(
                    (m.ROOT/row["path"]).read_text(encoding="utf-8"))
            else:
                self.assertIn(sid,("4024","4025"))
                body="오프라인 시험 전용 가상 임시회의록입니다. "*16
            return 200,official_html(body)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"monitor.json"
            with patch.object(m.platform,"system",return_value="Darwin"), \
                 patch.object(m.audit_stage_c,"audit",return_value={"status":"PASS"}):
                result=m.monitor(
                    read=fake_read,
                    scan_date=self.date,output=out,
                    discover=lambda out:self.discovery,
                    pause=lambda x:None,
                )
            self.assertEqual(result["status"],"PASS_REVIEW_CANDIDATES_PRESENT")
            self.assertEqual(result["actual_official_body_requests"],16)
            self.assertEqual(len(calls),16)
            self.assertEqual(result["new_bodies_readable"],2)
            self.assertEqual(result["body_failures"],[])
            self.assertEqual(result["body_unmodified"],14)
            self.assertEqual(result["body_change_candidates"],[])
            self.assertTrue(out.is_file())


if __name__=="__main__":
    unittest.main()
