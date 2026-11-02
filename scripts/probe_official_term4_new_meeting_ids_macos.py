"""Bounded official term-4 read-only inventory vs all 2,339 saved meeting IDs.

Real HTTPS requests only on GitHub macOS runner using the ORIGINAL collector TLS
configuration (TLS>=1.2, DEFAULT cipher set, verified official certificate).
No full historical term 1-3 crawl, no live body fetch, no source file edits,
no reclassification, no production run_sync and no scheduled execution.

One official term-tree root, one term-4 session tree, every returned term-4
session branch (max 12) and every returned committee branch (max 18/session).
Maximum 80 requests, <=2 MiB each, 12 s/request, zero retries, 0.35 s gap.
Any incomplete branch, duplicate, invalid status, or request failure is
explicitly inconclusive; absence in partial discovery is NEVER deletion.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import platform
import re
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from probe_term4_branch_shape import query as official_query

INDEX=ROOT/"indexes/integrated/meetings.json"
OUTPUT=ROOT/"reports/official-term4-new-meeting-id-discovery-20261102.json"
HOST="councilrec.cheongju.go.kr"
MAX_CALLS=80
MAX_SESSIONS=12
MAX_COMMITTEES_PER_SESSION=18
INTER_REQUEST_PAUSE=0.35
OFFICIAL_BASE="https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="
DATE_PATTERN=re.compile(r"20\d{2}\.\d{2}\.\d{2}")


def _vars(node:dict)->dict:
    return {k:v for k,v in node.items() if k.startswith("var")}


def _id_sort(value:str):
    return (0,int(value)) if value.isdigit() else (1,value)


def classify(saved_rows:list[dict],official_rows:list[dict],coverage_complete:bool)->dict:
    """Pure classification: candidate additions/changes, never auto-apply."""
    saved={str(r["source_id"]):r for r in saved_rows}
    if len(saved)!=len(saved_rows):
        raise ValueError("Duplicate saved source ID")
    old_four={sid:r for sid,r in saved.items() if int(r["term"])==4}
    live={}
    dupes=[]
    errors=[]
    for row in official_rows:
        sid=str(row.get("source_id") or "")
        if not sid.isdigit():
            errors.append("Official leaf source ID missing/invalid")
            continue
        if sid in live:
            dupes.append(sid)
            continue
        if row.get("publication_status") not in ("published","provisional"):
            errors.append(f"{sid}: invalid official leaf var09")
        live[sid]=row
    new_ids=[]
    other_term_ids=[]
    status_changes=[]
    metadata_changes=[]
    unchanged=[]
    for sid,item in live.items():
        old=saved.get(sid)
        if old is None:
            new_ids.append({
                "source_id":sid,
                "official_url":item["official_url"],
                "official_date":item["date"],
                "official_status":item["publication_status"],
                "official_title":item["title"],
                "official_session":item["session"],
                "official_committee_code":item["committee_code"],
                "action":"NEW_ID_CANDIDATE_READ_ONLY_BODY_VERIFICATION_REQUIRED",
                "auto_apply":False,
            })
            continue
        if int(old["term"])!=4:
            other_term_ids.append({
                "source_id":sid,
                "saved_term":old["term"],
                "live_term":4,
                "action":"POSSIBLE_PATH_OR_TERM_RECLASSIFICATION_REVIEW_NO_AUTOMATION",
            })
            continue
        if old["publication_status"]!=item["publication_status"]:
            status_changes.append({
                "source_id":sid,
                "stored_status":old["publication_status"],
                "live_official_status":item["publication_status"],
                "action":"VERIFY_NEW_OFFICIAL_BODY_AND_VERSION_PRESERVE_BEFORE_APPLY",
                "auto_apply":False,
            })
        fields={
            "title":(old.get("title"),item["title"]),
            "date":(old.get("date"),item["date"]),
            "committee_code":(old.get("committee_code"),item["committee_code"]),
            "official_url":(old.get("official_url"),item["official_url"]),
        }
        changed={k:{"saved":v[0],"live":v[1]} for k,v in fields.items() if v[0]!=v[1]}
        if changed:
            metadata_changes.append({"source_id":sid,"differences":changed,
                                     "action":"REVIEW_OFFICIAL_METADATA_AND_KEEP_ORIGINAL_VERSION",
                                     "auto_apply":False})
        if not changed and old["publication_status"]==item["publication_status"]:
            unchanged.append(sid)
    missing=sorted(set(old_four)-set(live),key=_id_sort) if coverage_complete else []
    if dupes or errors:
        coverage_complete=False
        missing=[]
    conclusion=(
        "INCONCLUSIVE_PARTIAL_OFFICIAL_TERM4_INVENTORY" if not coverage_complete
        else "TERM4_INVENTORY_HAS_REVIEW_CANDIDATES" if
        (new_ids or other_term_ids or status_changes or metadata_changes or missing)
        else "NO_NEW_OR_CHANGED_TERM4_METADATA_IN_OFFICIAL_INVENTORY"
    )
    return {
        "saved_total_meeting_count":len(saved),
        "saved_term4_count":len(old_four),
        "observed_term4_official_unique_ids":len(live),
        "official_term4_coverage_complete":coverage_complete,
        "observed_in_other_term_saved_ids":other_term_ids,
        "new_source_id_candidates":sorted(new_ids,key=lambda x:_id_sort(x["source_id"])),
        "status_change_candidates":sorted(status_changes,key=lambda x:_id_sort(x["source_id"])),
        "metadata_change_candidates":sorted(metadata_changes,key=lambda x:_id_sort(x["source_id"])),
        "verified_metadata_unchanged_ids":sorted(unchanged,key=_id_sort),
        "missing_saved_term4_ids_full_branch_only":missing,
        "unknown_or_duplicate_issues":errors+["duplicate_id:"+i for i in dupes],
        "conclusion":conclusion,
        "production_archive_update_allowed":False,
        "existing_source_files_modified":False,
    }


def discover(read=official_query,sleep=time.sleep,out:Path=OUTPUT)->dict:
    if platform.system()!="Darwin":
        raise RuntimeError("Refusing official live requests outside macOS")
    baseline=json.loads(INDEX.read_text(encoding="utf-8"))
    if len(baseline)!=2339:
        raise ValueError("Expected 2339 saved sources before live comparison")
    if sum(int(x["term"])==4 for x in baseline)!=50:
        raise ValueError("Expected 50 term-4 saved source rows")
    report={
        "schema":"official-term4-new-ids-bounded-live-inventory/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "official_source":HOST,
        "runner":"GitHub-hosted macOS; original collector TLS DEFAULT with verification",
        "selection":"All live official term-4 sessions returned; no historical terms 1,2,3 scanned",
        "request_limit":MAX_CALLS,
        "requests_attempted":0,
        "retries":0,
        "request_timeout_seconds":12,
        "max_sessions":MAX_SESSIONS,
        "max_committees_per_session":MAX_COMMITTEES_PER_SESSION,
        "raw_response_cap_bytes_per_request":2*1024*1024,
        "session_count":None,
        "committee_branches_visited":0,
        "leaf_count":0,
        "branch_errors":[],
        "all_term4_session_branches_exhausted":False,
        "raw_meeting_bodies_downloaded":0,
        "archive_files_modified":False,
        "production_sync_enabled":False,
        "operational_release_authorized":False,
    }
    rows=[]
    def one(payload:dict)->list[dict]:
        if report["requests_attempted"]>=MAX_CALLS:
            raise RuntimeError("MAX_REQUEST_LIMIT_REACHED")
        if report["requests_attempted"]:
            sleep(INTER_REQUEST_PAUSE)
        report["requests_attempted"]+=1
        return read(payload)
    try:
        roots=one({"var10":"SvcMntsTreeGnrtn"})
        term=[r for r in roots if str(r.get("var01"))=="4" and not r.get("var03")]
        if len(term)!=1:
            raise ValueError("Expected exactly one official term-4 root")
        root=term[0]
        sessions=one(_vars(root))
        if len(sessions)>MAX_SESSIONS:
            raise ValueError("Official term-4 sessions exceeded approved 12-session cap")
        if not sessions:
            raise ValueError("No official term-4 sessions")
        report["session_count"]=len(sessions)
        seen_sessions=set()
        for session in sessions:
            if str(session.get("var01"))!="4" or not str(session.get("var03") or "").isdigit():
                raise ValueError("Official session lacks term=4 or numeric session number")
            ses=str(session["var03"])
            if ses in seen_sessions:
                raise ValueError("Duplicate official term-4 session "+ses)
            seen_sessions.add(ses)
            committees=one(_vars(session))
            if len(committees)>MAX_COMMITTEES_PER_SESSION:
                raise ValueError("Official session "+ses+" exceeded approved committee cap")
            for committee in committees:
                code=str(committee.get("var02") or "")
                if (str(committee.get("var03"))!=ses or str(committee.get("var01"))!="4"
                     or not code):
                    raise ValueError(f"Unexpected committee hierarchy under term4 session {ses}")
                leaves=one(_vars(committee))
                report["committee_branches_visited"]+=1
                for leaf in leaves:
                    sid=str(leaf.get("var12") or "")
                    if not sid.isdigit():
                        raise ValueError(
                            f"Unexpected nested/non-leaf official source under session {ses}, committee {code}"
                        )
                    flag=str(leaf.get("var09") or "")
                    if flag not in ("Y","N"):
                        raise ValueError(f"Unexpected publication code for official source {sid}")
                    text=str(leaf.get("text") or "")
                    match=DATE_PATTERN.search(text)
                    if not match:
                        raise ValueError(f"Missing leaf meeting date for official source {sid}")
                    meeting_date=match.group(0).replace(".","-")
                    dt.date.fromisoformat(meeting_date)
                    title=" ".join(str(x.get("text") or "").strip() for x in (root,session,committee,leaf)).strip()
                    rows.append({
                        "source_id":sid,
                        "date":meeting_date,
                        "title":title,
                        "committee_code":code,
                        "session":ses,
                        "publication_status":"published" if flag=="Y" else "provisional",
                        "official_url":OFFICIAL_BASE+sid,
                    })
        report["all_term4_session_branches_exhausted"]=True
    except Exception as exc:
        report["branch_errors"].append({"exception_type":type(exc).__name__,
                                        "message":str(exc)[:240]})
    report["leaf_count"]=len(rows)
    classified=classify(baseline,rows,coverage_complete=report["all_term4_session_branches_exhausted"])
    report.update(classified)
    report["warnings"]=[
        "This checks official term 4 only; no conclusion about new source IDs for terms 1-3.",
        "Even complete leaf enumeration does not test changes to existing meeting body text; compare body hashes separately.",
        "Missing saved IDs represent official metadata discrepancy, not evidence of deletion; source records never automatically removed.",
    ]
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    print(json.dumps(discover(),ensure_ascii=False,indent=2))
