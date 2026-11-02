"""Fail-closed historic term 1-3 rolling official metadata monitor, macOS.

This is NOT a whole 1-3-term nightly audit. It inspects exactly ONE complete
selected session subtree per historic term per successful day, with a stable
date-based rotation and a strict all-request cap. No source body or archive
file is downloaded/changed, and no absence is treated as deletion.

Source: the real Cheongju Council official generation-tree endpoint, with the
same TLS context/certificate verification as the validated original collector.
Metadata changes, newly appearing IDs, duplicate leaf IDs, branch failures and
session-tree instability become review-only/blocked reports. A complete
historical TERM inventory is NOT claimed from a one-day session sample.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import re
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from probe_term4_branch_shape import query as official_query

DEFAULT_OUT=ROOT/"reports/official-historical-rolling-readonly-latest.json"
HISTORIC_TERMS=(1,2,3)
MAX_REQUESTS=90
MAX_SESSIONS_PER_TERM=160
MAX_COMMITTEES_PER_SESSION=26
REQUEST_DELAY_SECONDS=0.35
DATE_PATTERN=re.compile(r"20\d{2}\.\d{2}\.\d{2}")
URL_BASE="https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="
ANCHOR=dt.date(2026,11,2)


def official_vars(node:dict)->dict:
    return {k:v for k,v in node.items() if k.startswith("var")}


def select_session(sessions:list[dict],term:int,day:dt.date)->tuple[dict,int]:
    if not sessions or len(sessions)>MAX_SESSIONS_PER_TERM:
        raise ValueError(f"Term {term}: empty or excessive sessions")
    numbers=[str(row.get("var03") or "") for row in sessions]
    if any(not v.isdigit() for v in numbers) or len(set(numbers))!=len(numbers):
        raise ValueError(f"Term {term}: invalid or repeated official session numbers")
    if any(str(row.get("var01"))!=str(term) for row in sessions):
        raise ValueError(f"Term {term}: wrong term in session branch")
    sorted_sessions=sorted(sessions,key=lambda r:int(r["var03"]))
    index=(day-ANCHOR).days%len(sorted_sessions)
    return sorted_sessions[index],index


def compare_branch(saved:list[dict],observed:list[dict],term:int,session:str)->dict:
    by_id={str(row["source_id"]):row for row in saved}
    if len(by_id)!=len(saved):
        raise ValueError("Saved official source IDs are duplicated")
    live_ids=set()
    changed=[]
    new=[]
    duplicates=[]
    reclassified=[]
    unchanged=0
    for item in observed:
        sid=item["source_id"]
        if sid in live_ids:
            duplicates.append(sid)
            continue
        live_ids.add(sid)
        old=by_id.get(sid)
        if old is None:
            new.append({
                "source_id":sid,
                "term":term,"session":session,
                "official_url":item["official_url"],
                "official_date":item["date"],
                "official_status":item["publication_status"],
                "official_title":item["title"],
                "action":"REVIEW_ONLY_NO_AUTO_IMPORT",
            })
        elif int(old["term"])!=term:
            reclassified.append({
                "source_id":sid,"saved_term":old["term"],"official_term":term,
                "action":"VERIFY_OFFICIAL_TERM_BEFORE_ANY_UPDATE",
            })
        else:
            diff={}
            for key in ("title","date","committee_code","publication_status","official_url"):
                if old.get(key)!=item.get(key):
                    diff[key]={"saved":old.get(key),"official":item.get(key)}
            if diff:
                changed.append({"source_id":sid,"differences":diff,
                    "action":"VERIFY_OFFICIAL_BODY_AND_IMMUTABLE_REVISION_BEFORE_APPLY"})
            else:
                unchanged+=1
    return {
        "term":term,"session":session,
        "official_leaf_count":len(observed),
        "official_unique_ids":len(live_ids),
        "metadata_unchanged":unchanged,
        "new_id_candidates":new,
        "metadata_or_status_candidates":changed,
        "cross_term_id_candidates":reclassified,
        "duplicate_official_ids":duplicates,
        "missing_saved_ids_claimed":[],
        "snapshot_scope":"ONE FULL SELECTED SESSION ONLY; no whole-term deletion claim",
    }


def scan(read=official_query,pause=time.sleep,day=None,out=DEFAULT_OUT)->dict:
    if platform.system()!="Darwin":
        raise RuntimeError("OFFICIAL_HISTORICAL_READONLY_REQUIRES_MACOS")
    day=day or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    index=ROOT/"indexes/integrated/meetings.json"
    saved=json.loads(index.read_text(encoding="utf-8"))
    if len(saved)<2339:
        raise ValueError("Current historical archive unexpectedly smaller than initial 2339")
    if len({str(r["source_id"]) for r in saved})!=len(saved):
        raise ValueError("Duplicate saved official source IDs")
    report={
        "schema":"cheongju-official-historical-session-rotation-readonly/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "date_kst":day.isoformat(),
        "scope":"one complete official session selected per term 1,2,3",
        "terms":[1,2,3],
        "source_archive_count":len(saved),
        "max_requests":MAX_REQUESTS,
        "requests_attempted":0,
        "retries":0,
        "sessions_per_term_per_day":1,
        "selected_session_branches":[],
        "roots_found":[],
        "branch_errors":[],
        "all_three_selected_sessions_complete":False,
        "root_session_numbers_collected":False,
        "new_id_candidates":[],
        "metadata_or_status_candidates":[],
        "cross_term_id_candidates":[],
        "duplicate_official_ids":[],
        "whole_terms_completely_scanned":[],
        "any_missing_saved_id_inferred":False,
        "production_archive_modified":False,
        "production_sync_enabled":False,
        "scheduled_execution_enabled":False,
        "operational_release_authorized":False,
    }
    def call(payload):
        if report["requests_attempted"]>=MAX_REQUESTS:
            raise RuntimeError("HISTORICAL_OFFICIAL_REQUEST_CAP_REACHED")
        if report["requests_attempted"]:
            pause(REQUEST_DELAY_SECONDS)
        report["requests_attempted"]+=1
        return read(payload)

    try:
        roots=call({"var10":"SvcMntsTreeGnrtn"})
        selected={}
        for term in HISTORIC_TERMS:
            root=[r for r in roots
                  if str(r.get("var01"))==str(term) and not r.get("var03")]
            if len(root)!=1:
                raise ValueError(f"Missing/duplicate historic term root {term}")
            selected[term]=root[0]
        report["roots_found"]=list(selected)
        for term,root in sorted(selected.items()):
            sessions=call(official_vars(root))
            item,index=select_session(sessions,term,day)
            report["selected_session_branches"].append({
                "term":term,
                "official_session_count":len(sessions),
                "selected_session_number":str(item["var03"]),
                "rotation_index":index,
                "full_term_cycle_days_if_daily_success":len(sessions),
                "inspection_status":"PENDING",
            })
            report["selected_session_branches"][-1]["session_node"]=item
        report["root_session_numbers_collected"]=True
        complete_branches=[]
        for entry in report["selected_session_branches"]:
            term=entry["term"]
            session=str(entry["selected_session_number"])
            session_node=entry.pop("session_node")
            committees=call(official_vars(session_node))
            if len(committees)>MAX_COMMITTEES_PER_SESSION:
                raise ValueError(f"Term {term} session {session} too many committee nodes")
            all_leaves=[]
            codes=set()
            for committee in committees:
                code=str(committee.get("var02") or "")
                if (str(committee.get("var01"))!=str(term)
                    or str(committee.get("var03"))!=session or not code):
                    raise ValueError(f"Invalid committee navigation term {term} session {session}")
                if code in codes:
                    raise ValueError(f"Duplicate committee code term {term} session {session}")
                codes.add(code)
                leaves=call(official_vars(committee))
                for leaf in leaves:
                    sid=str(leaf.get("var12") or "")
                    if not sid.isdigit():
                        raise ValueError(f"Non-leaf or invalid ID under {term}/{session}/{code}")
                    flag=leaf.get("var09")
                    if flag not in ("Y","N"):
                        raise ValueError(f"Unknown official publication code {sid}")
                    text=str(leaf.get("text") or "")
                    match=DATE_PATTERN.search(text)
                    if not match:
                        raise ValueError(f"Official meeting date missing {sid}")
                    date=match.group(0).replace(".","-")
                    dt.date.fromisoformat(date)
                    title=" ".join(str(z.get("text") or "").strip()
                                   for z in (selected[term],session_node,committee,leaf))
                    all_leaves.append({
                        "source_id":sid,
                        "title":title,
                        "term":term,
                        "session":session,
                        "committee_code":code,
                        "publication_status":"published" if flag=="Y" else "provisional",
                        "official_url":URL_BASE+sid,
                        "date":date,
                    })
            observed=compare_branch(saved,all_leaves,term,session)
            if observed["duplicate_official_ids"]:
                raise ValueError(f"Duplicate official leaf ID term {term} session {session}")
            entry.update({k:v for k,v in observed.items() if k not in ("term","session")})
            entry["inspection_status"]="COMPLETE"
            complete_branches.append(entry)
            report["new_id_candidates"].extend(observed["new_id_candidates"])
            report["metadata_or_status_candidates"].extend(observed["metadata_or_status_candidates"])
            report["cross_term_id_candidates"].extend(observed["cross_term_id_candidates"])
        report["all_three_selected_sessions_complete"]=len(complete_branches)==3
        if any((report["new_id_candidates"],report["metadata_or_status_candidates"],
                report["cross_term_id_candidates"])):
            report["status"]="PASS_SCOPED_REVIEW_CANDIDATES_PRESENT"
        else:
            report["status"]="PASS_SCOPED_NO_CHANGES_OBSERVED"
    except Exception as err:
        for entry in report["selected_session_branches"]:
            entry.pop("session_node",None)
        report["branch_errors"].append({
            "type":type(err).__name__,
            "reason":str(err)[:220],
        })
        report["status"]="BLOCKED_INCOMPLETE_OFFICIAL_HISTORIC_SESSION_INSPECTION"
    report["provenance_limits"]=[
        "Only 1 session per historical term inspected per run, NOT all 1-3 term inventories.",
        "Official session counts and per-run selected session numbers are observed, not inferred.",
        "No deletion conclusions from missing/unchecked historical meeting IDs.",
        "A full theoretical cycle requires consecutive successful days with stable session lists; it has not yet been completed.",
        "This probe does not fetch or verify meeting body text.",
    ]
    out=Path(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=DEFAULT_OUT)
    args=parser.parse_args()
    report=scan(out=args.output)
    print(json.dumps({
        "status":report["status"],
        "date_kst":report["date_kst"],
        "official_requests":report["requests_attempted"],
        "sessions":[{"term":row["term"],
                     "number":row["selected_session_number"],
                     "count":row["official_session_count"],
                     "status":row["inspection_status"]}
                    for row in report["selected_session_branches"]],
        "new_ids":[row["source_id"] for row in report["new_id_candidates"]],
        "changed_ids":[row["source_id"] for row in report["metadata_or_status_candidates"]],
        "errors":report["branch_errors"],
    },ensure_ascii=False,indent=2))
    if report["status"].startswith("BLOCKED_"):
        print("::error title=Historical official tree incomplete::No archive publication permitted.")
        raise SystemExit(1)
    if report["status"]=="PASS_SCOPED_REVIEW_CANDIDATES_PRESENT":
        print("::warning title=Historical official change candidates::Review official source IDs; nothing published.")


if __name__=="__main__":
    main()
