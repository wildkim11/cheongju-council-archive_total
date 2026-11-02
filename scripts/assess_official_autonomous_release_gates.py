"""Machine-readable safety gates for Cheongju official minutes autonomous rollout.

This command NEVER enables a schedule or production publishing. It reads the
source-archive integrity, historical/term4 LIVE QA evidence, isolated 2342-body
rehearsal evidence and optional cumulative daily operational proof.

Even if all technical gates pass, production auto-updates require a distinct
user-approved release artifact. No implicit approval from green CI runs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/official-autonomous-release-readiness-latest.json"
HISTORY=ROOT/"reports/official-historical-rolling-readonly-latest.json"
CURRENT=ROOT/"reports/official-incremental-monitor-readonly-latest.json"
REHEARSAL=ROOT/"reports/official-real-three-new-2342-full-copy-rehearsal-20261102.json"
OPERATIONS=ROOT/"reports/operations/daily"
EVIDENCE=ROOT/"config/autonomous_official_release_evidence.json"
PER_TERM=(1,2,3)


def load_optional(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def rolling_coverage(items:list[dict])->dict:
    """Exhaustive historic session coverage requires real dated PASS proof."""
    observed={str(i):set() for i in PER_TERM}
    counts={}
    valid_dates=set()
    invalid_days=[]
    for item in items:
        day=item.get("date_kst")
        if (item.get("status") not in (
                "PASS_SCOPED_NO_CHANGES_OBSERVED",
                "PASS_SCOPED_REVIEW_CANDIDATES_PRESENT")
            or not item.get("all_three_selected_sessions_complete")
            or not isinstance(day,str)):
            invalid_days.append(day)
            continue
        try:
            dt.date.fromisoformat(day)
        except ValueError:
            invalid_days.append(day)
            continue
        branches=item.get("selected_session_branches",[])
        if set(row.get("term") for row in branches)!={1,2,3}:
            invalid_days.append(day)
            continue
        if any(row.get("inspection_status")!="COMPLETE" for row in branches):
            invalid_days.append(day)
            continue
        changed_counts=False
        for row in branches:
            term=str(row["term"])
            size=row["official_session_count"]
            if not isinstance(size,int) or size<=0 or size>160:
                changed_counts=True
                continue
            if term in counts and counts[term]!=size:
                changed_counts=True
            counts[term]=size
        if changed_counts:
            invalid_days.append(day)
            continue
        valid_dates.add(day)
        for row in branches:
            term=str(row["term"])
            observed[term].add(str(row["selected_session_number"]))
    covered={term:len(observed[str(term)]) for term in PER_TERM}
    targets={term:counts.get(str(term)) for term in PER_TERM}
    complete=bool(targets) and all(
        targets.get(term) is not None and covered[term]>=targets[term]
        for term in PER_TERM)
    return {
        "valid_distinct_days":len(valid_dates),
        "checked_session_counts":covered,
        "current_official_session_totals":targets,
        "full_historical_cycle_coverage_confirmed":complete,
        "rejected_or_failed_days":invalid_days,
        "scope_limit":"Session metadata only, not full historical meeting body SHA checks",
    }


def evaluate(history:dict|None,current:dict|None,
             rehearsal:dict|None,daily:list[dict],
             deployment:dict|None)->dict:
    coverage=rolling_coverage(daily)
    flags={
        "live_term4_full_catalog_and_bounded_viewer_checks":bool(current
          and current.get("status","").startswith("PASS_")
          and current.get("official_term4_coverage_complete")
          and current.get("actual_official_body_requests",99)<=20
          and current.get("official_term4_inventory_requests",99)<=80
          and not current.get("errors")
          and not current.get("body_failures")),
        "live_term1_2_3_one_session_each":bool(history
          and history.get("all_three_selected_sessions_complete")
          and history.get("requests_attempted",99)<=90
          and not history.get("branch_errors")
          and history.get("status","").startswith("PASS_")),
        "live_term1_2_3_full_cycle_covered":coverage["full_historical_cycle_coverage_confirmed"],
        "full_2342_isolated_real_source_sha_and_analyzer_qa":bool(rehearsal
          and rehearsal.get("status")=="PASS"
          and rehearsal.get("copy_source_count")==2342
          and rehearsal.get("copy_sha256_files_verified")==2342
          and rehearsal.get("copy_sha256_bodies_verified")==2342
          and rehearsal.get("copy_analyzer_meeting_rows")==2342
          and not rehearsal.get("archive_root_modified")),
        "rollback_on_sigkill_preserves_original_2339":bool(rehearsal
          and rehearsal.get("crash_recovery",{}).get("recovered_stage_c")=="PASS"
          and rehearsal.get("crash_recovery",{}).get(
            "prior_original_source_file_hashes_restored")==2339),
        "automatic_default_branch_schedule_observed":bool(deployment
          and deployment.get("verified_scheduled_run_on_default_branch") is True),
        "failure_notification_delivery_verified":bool(deployment
          and deployment.get("failure_notification_received_and_acknowledged") is True),
        "seven_successful_scheduled_day_runs":bool(deployment
          and isinstance(deployment.get("successful_consecutive_schedule_days"),int)
          and deployment["successful_consecutive_schedule_days"]>=7),
        "explicit_final_production_release_approval":bool(deployment
          and deployment.get("user_explicit_production_release_approval") is True),
    }
    # Deliberate separation: technical readiness is not authorization.
    operational_technical_ok=all(v for k,v in flags.items()
      if k!="explicit_final_production_release_approval")
    approved=operational_technical_ok and flags["explicit_final_production_release_approval"]
    return {
        "schema":"cheongju-autonomous-official-release-gates/1",
        # All gates above refer ONLY to the 2014+ integrated council minutes.
        # Pre-integration councils have separate numbering and source archives;
        # member-roster candidates are not a substitute for meeting bodies.
        "release_council_scope":"cheongju_integrated",
        "preintegration_legacy_minutes_included":False,
        "all_three_council_scopes_analyzer_release_authorized":False,
        "separate_scope_blockers":{
            "cheongju_old_city":"NO_OFFICIAL_MEETING_BODY_ARCHIVE_OR_LIVE_SYNC_QA",
            "cheongwon_old_county":"NO_OFFICIAL_MEETING_BODY_ARCHIVE_OR_LIVE_SYNC_QA",
        },
        "status":"AUTHORIZED_RELEASE_GATES_SATISFIED" if approved else "BLOCKED_PRE_RELEASE",
        "technical_ready":operational_technical_ok,
        "production_archive_auto_update_authorized":approved,
        "release_gates":flags,
        "blocked_gates":[k for k,v in flags.items() if not v],
        "historical_rolling_coverage":coverage,
        "notes":[
            "This report is descriptive only: it cannot unlock the real run_sync production interlock.",
            "A schedule added only on a feature branch will not execute automatically in GitHub Actions.",
            "GitHub Actions issues, web/email notifications and an actual recipient acknowledgement are different checks.",
            "No historical term can be declared fully covered from one rotating sample.",
            "True source body modifications and ongoing notifications require ongoing monitored evidence.",
        ],
    }


def run(output=OUT):
    history=load_optional(HISTORY)
    current=load_optional(CURRENT)
    rehearsal=load_optional(REHEARSAL)
    daily=[]
    if OPERATIONS.is_dir():
        for path in sorted(OPERATIONS.glob("historic-*.json")):
            obj=load_optional(path)
            if obj:daily.append(obj)
    if history:
        if not any(d.get("checked_at_utc")==history.get("checked_at_utc") for d in daily):
            daily.append(history)
    deployment=load_optional(EVIDENCE)
    outcome=evaluate(history,current,rehearsal,daily,deployment)
    outcome["evaluated_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":outcome["status"],
      "technical_ready":outcome["technical_ready"],
      "production_archive_auto_update_authorized":outcome["production_archive_auto_update_authorized"],
      "blocked_gates":outcome["blocked_gates"],
      "historical_coverage":outcome["historical_rolling_coverage"],
    },ensure_ascii=False,indent=2))
    return outcome


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,default=OUT)
    args=ap.parse_args()
    run(args.output)
