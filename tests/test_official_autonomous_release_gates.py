"""Offline tests: full historic cycle and explicit-release interlock requirements."""
import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import assess_official_autonomous_release_gates as g

def day_proof(offset):
    day=dt.date(2026,11,2)+dt.timedelta(days=offset)
    counts={1:34,2:36,3:32}
    starts={1:1,2:35,3:71}
    return {
        "status":"PASS_SCOPED_NO_CHANGES_OBSERVED",
        "date_kst":day.isoformat(),
        "all_three_selected_sessions_complete":True,
        "requests_attempted":29,
        "branch_errors":[],
        "selected_session_branches":[
            {
                "term":term,"inspection_status":"COMPLETE",
                "selected_session_number":str(starts[term]+offset%total),
                "official_session_count":total,
            }
            for term,total in counts.items()
        ],
    }

class ReleaseCriteriaTests(unittest.TestCase):
    def test_one_live_day_is_not_full_historic_term1_2_3_coverage(self):
        c=g.rolling_coverage([day_proof(0)])
        self.assertEqual(c["valid_distinct_days"],1)
        self.assertEqual(c["checked_session_counts"],{1:1,2:1,3:1})
        self.assertEqual(c["current_official_session_totals"],{1:34,2:36,3:32})
        self.assertFalse(c["full_historical_cycle_coverage_confirmed"])

    def test_all_36_successful_daily_samples_cover_all_official_sessions(self):
        c=g.rolling_coverage([day_proof(i) for i in range(36)])
        self.assertEqual(c["checked_session_counts"],{1:34,2:36,3:32})
        self.assertTrue(c["full_historical_cycle_coverage_confirmed"])
        self.assertEqual(c["valid_distinct_days"],36)

    def test_failed_day_is_rejected_and_never_used_as_coverage(self):
        failure=day_proof(0)
        failure["status"]="BLOCKED_INCOMPLETE_OFFICIAL_HISTORIC_SESSION_INSPECTION"
        c=g.rolling_coverage([failure])
        self.assertFalse(c["full_historical_cycle_coverage_confirmed"])
        self.assertEqual(c["valid_distinct_days"],0)
        self.assertIn(failure["date_kst"],c["rejected_or_failed_days"])

    def test_even_perfect_technical_proof_requires_explicit_approval(self):
        current={
            "status":"PASS_REVIEW_CANDIDATES_PRESENT",
            "official_term4_coverage_complete":True,
            "actual_official_body_requests":17,
            "official_term4_inventory_requests":33,
            "errors":[],"body_failures":[],
        }
        hist=day_proof(0)
        real={
            "status":"PASS","copy_source_count":2342,
            "copy_sha256_files_verified":2342,"copy_sha256_bodies_verified":2342,
            "copy_analyzer_meeting_rows":2342,
            "archive_root_modified":False,
            "crash_recovery":{
                "recovered_stage_c":"PASS",
                "prior_original_source_file_hashes_restored":2339,
            },
        }
        deployment={
            "verified_scheduled_run_on_default_branch":True,
            "failure_notification_received_and_acknowledged":True,
            "successful_consecutive_schedule_days":7,
            "user_explicit_production_release_approval":False,
        }
        r=g.evaluate(hist,current,real,[day_proof(i) for i in range(36)],deployment)
        self.assertTrue(r["technical_ready"])
        self.assertFalse(r["production_archive_auto_update_authorized"])
        self.assertEqual(r["blocked_gates"],["explicit_final_production_release_approval"])
        deployment["user_explicit_production_release_approval"]=True
        r2=g.evaluate(hist,current,real,[day_proof(i) for i in range(36)],deployment)
        self.assertTrue(r2["production_archive_auto_update_authorized"])
        # Even an approved integrated-only rollout cannot claim that
        # the two pre-integration councils' meeting archives exist.
        self.assertEqual(r2["release_council_scope"],"cheongju_integrated")
        self.assertFalse(r2["preintegration_legacy_minutes_included"])
        self.assertFalse(r2["all_three_council_scopes_analyzer_release_authorized"])
        self.assertEqual(set(r2["separate_scope_blockers"]),{
            "cheongju_old_city","cheongwon_old_county",
        })

    def test_empty_sources_never_authorized(self):
        r=g.evaluate(None,None,None,[],None)
        self.assertEqual(r["status"],"BLOCKED_PRE_RELEASE")
        self.assertFalse(r["technical_ready"])
        self.assertFalse(r["production_archive_auto_update_authorized"])

    def test_inconsistent_session_counts_are_rejected(self):
        items=[day_proof(0),day_proof(1)]
        items[1]["selected_session_branches"][0]["official_session_count"]=99
        c=g.rolling_coverage(items)
        self.assertIn(items[1]["date_kst"],c["rejected_or_failed_days"])
        self.assertFalse(c["full_historical_cycle_coverage_confirmed"])

if __name__=="__main__":
    unittest.main()
