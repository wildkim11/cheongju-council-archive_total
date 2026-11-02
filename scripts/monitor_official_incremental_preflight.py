"""Integrated, read-only official minutes monitor (pre-production, macOS).

Checks all current fourth-term official metadata branches, all saved provisional
minutes, any detected status/metadata changes, any new official IDs and a
deterministic rolling sample of published meeting bodies across terms 1-4.

This is a CANDIDATE DETECTOR, NOT AN ARCHIVE PUBLISHER:
- no official-source mutation; no old Markdown/index/export mutation;
- no production run_sync call and no activation of scheduled collection;
- TLS verification is enabled, using original successful collector TLS options;
- no retries; strict per-request time, response, and aggregate request limits;
- no removal inference from partial source inventories;
- failures are fail-closed, with a durable JSON result and nonzero exit code;
- warnings / Actions step summary may expose only IDs, counts, and SHA hashes.
Full body revalidation of ALL previously published meetings is NOT achieved by
one run; rolling samples improve coverage only over future successful runs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import json
import platform
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
import audit_stage_c
import collect_integrated_minutes as original
import probe_official_term4_new_meeting_ids_macos as listing

HOST = "councilrec.cheongju.go.kr"
VIEWER = "/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="
DEFAULT_OUT = ROOT/"reports/official-incremental-monitor-readonly-latest.json"
MAX_TOTAL_BODY_GETS = 20
MAX_NEW_IDS = 8
MAX_SAVED_PROVISIONAL = 10
SAMPLE_FOURTH_TERM = 4
SAMPLE_OLDER_TERMS = 4
MAX_HTML_BYTES = 8 * 1024 * 1024
GET_DELAY_SECONDS = 0.35
GET_TIMEOUT_SECONDS = 12
SCOPE = "cheongju_integrated"
ID_PATTERN = re.compile(r"^[0-9]+$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected_rotation(items: list[dict], width: int, ordinal: int) -> list[dict]:
    """Date-based rotation avoids writing persistent cursor into production."""
    if width <= 0 or not items:
        return []
    ordered = sorted(items, key=lambda x: int(x["source_id"]))
    start = ((ordinal - dt.date(2026, 11, 2).toordinal()) * width) % len(ordered)
    return [ordered[(start + idx) % len(ordered)]
            for idx in range(min(width, len(ordered)))]


def plan_body_reads(saved_rows: list[dict], discovery: dict,
                    scan_date: dt.date) -> dict:
    """Fail closed if metadata discovery is incomplete or budget cannot fit."""
    if not discovery.get("official_term4_coverage_complete"):
        raise ValueError("INCOMPLETE_OFFICIAL_TERM4_TREE")
    if discovery.get("branch_errors") or discovery.get("unknown_or_duplicate_issues"):
        raise ValueError("OFFICIAL_TERM4_TREE_ERROR_OR_DUPLICATE")
    if discovery.get("missing_saved_term4_ids_full_branch_only"):
        raise ValueError("SAVED_OFFICIAL_ID_MISSING_FROM_CURRENT_TERM4_TREE_REVIEW")
    if discovery.get("observed_in_other_term_saved_ids"):
        raise ValueError("OFFICIAL_TERM_RECLASSIFICATION_REVIEW")
    if discovery.get("saved_total_meeting_count") != len(saved_rows):
        raise ValueError("ARCHIVE_COUNT_CHANGED_DURING_OFFICIAL_LISTING")
    saved = {str(row["source_id"]):row for row in saved_rows}
    if len(saved) != len(saved_rows):
        raise ValueError("DUPLICATED_SAVED_SOURCE_ID")
    new = discovery.get("new_source_id_candidates", [])
    if len(new) > MAX_NEW_IDS:
        raise ValueError("NEW_SOURCE_CANDIDATES_EXCEED_READ_BUDGET")
    for candidate in new:
        sid = str(candidate["source_id"])
        if sid in saved or not ID_PATTERN.fullmatch(sid):
            raise ValueError("OFFICIAL_NEW_SOURCE_ID_COLLISION_OR_MALFORMED")
        if candidate.get("official_url") != original.BASE + VIEWER + sid:
            raise ValueError("UNEXPECTED_NEW_OFFICIAL_URL")
    provisional = [row for row in saved_rows
                   if row["publication_status"]=="provisional"]
    if len(provisional) > MAX_SAVED_PROVISIONAL:
        raise ValueError("SAVED_PROVISIONAL_COUNT_EXCEEDS_READ_BUDGET")
    term4 = [row for row in saved_rows
             if row["term"]==4 and row["publication_status"]=="published"]
    older = [row for row in saved_rows
             if row["term"] in (1,2,3) and row["publication_status"]=="published"]
    sample = selected_rotation(term4,SAMPLE_FOURTH_TERM,scan_date.toordinal())
    sample += selected_rotation(older,SAMPLE_OLDER_TERMS,scan_date.toordinal())
    status = discovery.get("status_change_candidates",[])
    meta = discovery.get("metadata_change_candidates",[])
    to_check = {}
    purposes = {}

    def add(sid, reason):
        sid = str(sid)
        if not ID_PATTERN.fullmatch(sid):
            raise ValueError("BAD_OFFICIAL_ID_FOR_VIEWER")
        to_check[sid] = saved.get(sid)
        purposes.setdefault(sid,[]).append(reason)

    for record in new:
        add(record["source_id"],"new_source")
    for record in provisional:
        add(record["source_id"],"saved_provisional")
    for record in status:
        add(record["source_id"],"status_change")
    for record in meta:
        add(record["source_id"],"metadata_change")
    for record in sample:
        add(record["source_id"],"published_rotation")
    if len(to_check)>MAX_TOTAL_BODY_GETS:
        raise ValueError("REQUIRED_BODY_READS_EXCEED_20_REQUEST_BUDGET")
    return {
        "ordered_ids":sorted(to_check,key=int),
        "purposes":purposes,
        "new_source_ids":sorted((str(item["source_id"]) for item in new),key=int),
        "old_provisional_ids":sorted((str(item["source_id"]) for item in provisional),key=int),
        "published_sample_ids":sorted((str(item["source_id"]) for item in sample),key=int),
        "saved_by_id":to_check,
        "body_request_cap":MAX_TOTAL_BODY_GETS,
        "new_candidate_limit":MAX_NEW_IDS,
        "saved_provisional_limit":MAX_SAVED_PROVISIONAL,
    }


def read_one_official_body(source_id: str) -> tuple[int,bytes]:
    if not ID_PATTERN.fullmatch(source_id):
        raise ValueError("INVALID_SOURCE_ID")
    conn = http.client.HTTPSConnection(
        HOST, timeout=GET_TIMEOUT_SECONDS, context=original.TLS
    )
    try:
        conn.request("GET",VIEWER+source_id,headers={
            "User-Agent":"CheongjuCouncilArchive/0.1",
            "Content-Type":"application/x-www-form-urlencoded",
        })
        response = conn.getresponse()
        body = response.read(MAX_HTML_BYTES+1)
        if len(body)>MAX_HTML_BYTES:
            raise ValueError("OVERSIZED_OFFICIAL_VIEWER_RESPONSE")
        return response.status,body
    finally:
        conn.close()


def evaluate_official_body(source_id: str, row: dict|None,
                           http_status: int, raw: bytes, purpose: list[str]) -> dict:
    """Return provenance and content hash, but never store original body text."""
    result = {
        "source_id":source_id,
        "reason":purpose,
        "official_url":original.BASE+VIEWER+source_id,
        "http_status":http_status,
        "raw_response_bytes":len(raw),
        "raw_response_sha256":sha256(raw),
    }
    if http_status != 200:
        result["verification"]="HTTP_ERROR_NO_CONTENT_VERIFIED"
        result["error"]="HTTP_"+str(http_status)
        return result
    try:
        body = original.extract_minutes_body(raw.decode("utf-8-sig"))
        current = sha256(original.canonical(body).encode("utf-8"))
        result["body_characters"]=len(body)
        result["current_body_sha256"]=current
        result["previous_body_sha256"]=row.get("content_sha256") if row else None
        if row is None:
            result["verification"]="NEW_OFFICIAL_BODY_READABLE_REVIEW_ONLY"
            result["body_changed"]=None
        elif current != row["content_sha256"]:
            result["verification"]="EXISTING_OFFICIAL_BODY_CHANGED_REVIEW_REQUIRED"
            result["body_changed"]=True
        else:
            result["verification"]="EXISTING_OFFICIAL_BODY_UNCHANGED"
            result["body_changed"]=False
    except (UnicodeError,ValueError) as error:
        result["verification"]="OFFICIAL_VIEWER_PARSE_FAILED"
        result["error_type"]=type(error).__name__
        result["error"]=str(error)[:160]
    return result


def summarize(results: list[dict], discovery:dict) -> dict:
    unknown=[row for row in results if row.get("verification") in {
        "HTTP_ERROR_NO_CONTENT_VERIFIED","OFFICIAL_VIEWER_PARSE_FAILED"
    }]
    drift=[row for row in results
           if row.get("verification")=="EXISTING_OFFICIAL_BODY_CHANGED_REVIEW_REQUIRED"]
    return {
        "new_ids":discovery.get("new_source_id_candidates", []),
        "status_change_candidates":discovery.get("status_change_candidates", []),
        "metadata_change_candidates":discovery.get("metadata_change_candidates", []),
        "body_change_candidates":drift,
        "body_failures":unknown,
        "body_unmodified":sum(
            r.get("verification")=="EXISTING_OFFICIAL_BODY_UNCHANGED"
            for r in results
        ),
        "new_bodies_readable":sum(
            r.get("verification")=="NEW_OFFICIAL_BODY_READABLE_REVIEW_ONLY"
            for r in results
        ),
        "has_review_candidates":any((
            discovery.get("new_source_id_candidates",[]),
            discovery.get("status_change_candidates",[]),
            discovery.get("metadata_change_candidates",[]),
            drift,
        )),
    }


def current_official_listing(out):
    return listing.discover(out=out, baseline_policy="current")


def monitor(read=read_one_official_body, scan_date=None, output=DEFAULT_OUT,
            discover=current_official_listing, pause=time.sleep) -> dict:
    if platform.system() != "Darwin":
        raise RuntimeError("OFFICIAL_LIVE_READONLY_MONITOR_MACOS_ONLY")
    today=scan_date or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    report = {
        "schema":"cheongju-official-readonly-monitor-preproduction/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "date_local_kst":today.isoformat(),
        "environment":"macOS official collector TLS verification enabled",
        "mode":"READ_ONLY_REVIEW_CANDIDATES_NO_PUBLISH",
        "scope":"term4 entire official tree; saved provisional plus rolling published sample; NOT full historical body recheck",
        "archive_root_modified":False,
        "production_incremental_enabled":False,
        "schedule_enabled":False,
        "operational_release_authorized":False,
        "max_official_inventory_requests":listing.MAX_CALLS,
        "max_official_body_requests":MAX_TOTAL_BODY_GETS,
        "actual_official_body_requests":0,
        "retries":0,
        "body_results":[],
        "errors":[],
        "status":"INCONCLUSIVE",
    }
    try:
        saved=json.loads((ROOT/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
        if len(saved)<2339:
            raise ValueError("CURRENT_ARCHIVE_BELOW_INITIAL_2339_BASELINE")
        # Report only, not publication. The audit uses on-disk source checksums.
        audit=audit_stage_c.audit(ROOT)
        if audit["status"]!="PASS":
            raise RuntimeError("LOCAL_SOURCE_ARCHIVE_NOT_VALIDATED: "+repr(audit["errors"][:2]))
        report["saved_meeting_count"]=len(saved)
        with tempfile.TemporaryDirectory(prefix="cheongju-monitor-preflight-") as temp:
            tree_path=Path(temp)/"official-term4-list.json"
            tree=discover(out=tree_path)
        report["official_term4_inventory_requests"]=tree["requests_attempted"]
        report["official_term4_leaf_count"]=tree["observed_term4_official_unique_ids"]
        report["official_term4_coverage_complete"]=tree["official_term4_coverage_complete"]
        if tree["conclusion"]=="INCONCLUSIVE_PARTIAL_OFFICIAL_TERM4_INVENTORY":
            raise RuntimeError("OFFICIAL_TERM4_INVENTORY_INCONCLUSIVE: "+repr(tree.get("branch_errors")))
        plan=plan_body_reads(saved,tree,today)
        report["selected_ids"]=plan["ordered_ids"]
        report["published_rotation_ids"]=plan["published_sample_ids"]
        report["saved_provisional_ids"]=plan["old_provisional_ids"]
        report["body_results"]=[]
        for sid in plan["ordered_ids"]:
            if report["actual_official_body_requests"]:
                pause(GET_DELAY_SECONDS)
            report["actual_official_body_requests"]+=1
            try:
                status,raw=read(sid)
                report["body_results"].append(evaluate_official_body(
                    sid,plan["saved_by_id"][sid],status,raw,plan["purposes"][sid],
                ))
            except Exception as error:
                report["body_results"].append({
                    "source_id":sid,"reason":plan["purposes"][sid],
                    "verification":"OFFICIAL_CONNECTION_ERROR",
                    "error_type":type(error).__name__,
                    "error":str(error)[:160],
                })
                break
        report.update(summarize(report["body_results"],tree))
        if len(report["body_results"])!=len(plan["ordered_ids"]):
            raise RuntimeError("OFFICIAL_BODY_REQUESTS_INCOMPLETE")
        if any(result["verification"] in {
            "HTTP_ERROR_NO_CONTENT_VERIFIED","OFFICIAL_VIEWER_PARSE_FAILED",
            "OFFICIAL_CONNECTION_ERROR",
        } for result in report["body_results"]):
            raise RuntimeError("OFFICIAL_BODY_READ_OR_PARSE_ERROR")
        report["status"]=(
            "PASS_REVIEW_CANDIDATES_PRESENT" if report["has_review_candidates"]
            else "PASS_NO_CANDIDATES_IN_CHECKED_SCOPE"
        )
    except Exception as error:
        report["status"]="BLOCKED_INCONCLUSIVE_SOURCE_OR_BUDGET"
        report["errors"].append({
            "type":type(error).__name__,
            "reason":str(error)[:240],
        })
    report["warnings"]=[
        "This does not check all term 1-3 current official inventory branches.",
        "Historical published bodies are sampled: unchecked records cannot be asserted unchanged.",
        "Confirmed changes are review candidates only; no archived source is added or overwritten.",
        "A failed branch or viewer read blocks the monitor rather than implying deletion.",
    ]
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=DEFAULT_OUT)
    args=parser.parse_args()
    report=monitor(output=args.output)
    summary={
        "status":report["status"],
        "saved_meeting_count":report.get("saved_meeting_count"),
        "official_term4_leaf_count":report.get("official_term4_leaf_count"),
        "body_requests":report["actual_official_body_requests"],
        "new_source_ids":[r["source_id"] for r in report.get("new_ids",[])],
        "status_change_ids":[r["source_id"] for r in report.get("status_change_candidates",[])],
        "metadata_change_ids":[r["source_id"] for r in report.get("metadata_change_candidates",[])],
        "body_change_ids":[r["source_id"] for r in report.get("body_change_candidates",[])],
        "error_count":len(report["errors"])+len(report.get("body_failures",[])),
    }
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if report["status"]=="BLOCKED_INCONCLUSIVE_SOURCE_OR_BUDGET":
        print("::error title=Official minutes monitor blocked::No auto-collection or inference permitted.")
        raise SystemExit(1)
    if report["has_review_candidates"]:
        print("::warning title=Official minutes need review::Source IDs or body hashes changed; no archive update performed.")

if __name__=="__main__":
    main()
