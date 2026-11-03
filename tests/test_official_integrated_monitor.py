"""No-network safety tests for the pre-production macOS official monitor."""
from __future__ import annotations

from historical_snapshot import initial_meetings
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
    return initial_meetings()


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
        # Pin old-monitor rehearsals to an isolated synthetic body corpus so a
        # successful live update cannot invalidate historical fixture proofs.
        self.fixture_body=lambda sid: ("격리 회의록 시험 자료 "+str(sid)+" ")*30
        for row in self.saved:row['content_sha256']=m.sha256(audit_stage_c.canon(self.fixture_body(row['source_id'])).encode())
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        fixture=Path(folder.name);(fixture/'indexes/integrated').mkdir(parents=True)
        (fixture/'indexes/integrated/meetings.json').write_text(json.dumps(self.saved),encoding='utf-8')
        root_patch=patch.object(m,'ROOT',fixture);root_patch.start();self.addCleanup(root_patch.stop)
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
                body=self.fixture_body(sid)
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


    def test_monitor_current_listing_does_not_assume_permanent_2339_baseline(self):
        from unittest.mock import MagicMock
        marker=Path("/tmp/disposable-monitor-list.json")
        with patch.object(m.listing,"discover",return_value={"sample":"current"}) as fake:
            self.assertEqual(m.current_official_listing(marker),{"sample":"current"})
        fake.assert_called_once_with(out=marker,baseline_policy="current")

    def test_bounded_tree_accepts_future_2341_current_index_only_when_opted_in(self):
        # Synthetic INDEX rows: no official server or archived source files changed.
        advanced=list(self.saved)
        for sid in ("4024","4025"):
            advanced.append({"source_id":sid,"term":4,"publication_status":"provisional"})
        self.assertEqual(len(advanced),2341)
        def fake_tree(node):
            kind=node.get("var11")
            if node.get("var10")=="SvcMntsTreeGnrtn":
                return [{"var01":"4","var03":"","text":"제4대",
                         "var11":"SvcMntsTreeGnrtnSesn"}]
            if kind=="SvcMntsTreeGnrtnSesn":
                return [{"var01":"4","var03":"106","text":"제106회",
                         "var11":"SvcMntsTreeGnrtnCmmtNm"}]
            if kind=="SvcMntsTreeGnrtnCmmtNm":
                return [{"var01":"4","var03":"106","var02":"A010",
                         "text":"본회의","var11":"SvcMntsTreeGnrtnChasu"}]
            if kind=="SvcMntsTreeGnrtnChasu":
                return []
            raise AssertionError("Unexpected official-tree request")
        with tempfile.TemporaryDirectory() as td:
            index=Path(td)/"advanced-index.json"
            index.write_text(json.dumps(advanced),encoding="utf-8")
            output=Path(td)/"result.json"
            with patch.object(m.listing,"INDEX",index), \
                 patch.object(m.listing.platform,"system",return_value="Darwin"):
                with self.assertRaisesRegex(ValueError,"Expected 2339"):
                    m.listing.discover(read=fake_tree,sleep=lambda _ : None,out=output)
                r=m.listing.discover(
                    read=fake_tree,sleep=lambda _ : None,out=output,
                    baseline_policy="current",
                )
            self.assertEqual(r["saved_total_meeting_count"],2341)
            self.assertEqual(r["saved_term4_count"],52)
            self.assertEqual(r["requests_attempted"],4)
            self.assertEqual(r["baseline_policy"],"current")
            self.assertEqual(r["new_source_id_candidates"],[])
            self.assertEqual(r["conclusion"],"TERM4_INVENTORY_HAS_REVIEW_CANDIDATES")
            self.assertFalse(r["production_archive_update_allowed"])


if __name__=="__main__":
    unittest.main()
