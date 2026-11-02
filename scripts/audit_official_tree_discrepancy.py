"""Read-only audit of the 13 term-only meeting IDs against live official trees.

Inspect source-proven term/year discrepancies without changing canonical
meeting files, collection dates, indexes, or analyzer exports. macOS network
source access is expected for the optional --live mode.
"""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from collect_integrated_minutes import (
    _tree, fetch, inventory_by_term, inventory_by_year, merge_official_inventories
)

ROOT = Path(__file__).resolve().parents[1]
IDS = ("180", "508", "896", "1212", "1573", "1848", "1900",
       "2257", "2258", "2659", "2951", "3315", "3652")
SOURCE_PREFIX="https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="
END = re.compile(r"제\s*\d+\s*회[^\n()]{0,60}\(\s*(20\d{2}\.\s*\d{1,2}\.\s*\d{1,2})\s*~\s*(20\d{2}\.\s*\d{1,2}\.\s*\d{1,2})\s*\)")
DAY=re.compile(r"20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}")
 
def d(s):
    y,m,day=(int(v.strip()) for v in s.split("."))
    return dt.date(y,m,day)

def classify(row):
    title=row["title"]
    m=END.search(title)
    if not m:
        raise ValueError(f"Session date range not found in official title {row.get('source_id')}: {title}")
    start,end=d(m[1]),d(m[2])
    actual=dt.date.fromisoformat(row["date"])
    if end<start:
        raise ValueError(f"Session date range is reversed for {row['source_id']}")
    return {
        "source_id":str(row["source_id"]),
        "term":row["term"],
        "title":title,
        "committee_code":row.get("committee_code"),
        "meeting_type":row.get("meeting_type"),
        "meeting_date":row["date"],
        "session_start":start.isoformat(),
        "session_end":end.isoformat(),
        "days_after_session_end":(actual-end).days,
        "post_session":actual>end,
        "status":row["publication_status"],
        "official_url":row["official_url"],
        "path":row.get("path"),
        "index_sources":row.get("inventory_sources"),
    }

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def offline(root=ROOT):
    idx=read(root/"indexes/integrated/meetings.json")
    qa=read(root/"reports/integrated-sync.json")["inventory_qa"]
    by_id={str(x["source_id"]):x for x in idx}
    if len(by_id)!=len(idx):
        raise ValueError("Duplicate source IDs in canonical index")
    if set(qa["only_term"])!=set(IDS) or qa["only_year"] or len(idx)!=2339:
        raise ValueError("Unexpected source inventory discrepancy baseline")
    bad=[]
    ok=[]
    for x in idx:
        try:
            row=classify(x)
        except ValueError as e:
            bad.append({"source_id":str(x["source_id"]),"reason":str(e)[:250]})
            continue
        if x.get("inventory_sources")==["term"]:
            ok.append(row)
    if set(x["source_id"] for x in ok)!=set(IDS):
        raise ValueError("Exception set changed in canonical meeting index")
    not_post=[x["source_id"] for x in ok if not x["post_session"]]
    if not_post:
        raise ValueError(f"Some term-only records did NOT occur after session closure: {not_post}")
    shared_after=[]
    for x in idx:
        if x.get("inventory_sources")!=["term","year"]:
            continue
        try:
            candidate=classify(x)
        except ValueError:
            continue
        if candidate["post_session"]:
            shared_after.append({"source_id":candidate["source_id"],
                                 "term":candidate["term"],
                                 "meeting_date":candidate["meeting_date"],
                                 "session_end":candidate["session_end"],
                                 "days_after_session_end":candidate["days_after_session_end"]})
    return {
        "scope":"saved GitHub snapshot, offline",
        "total_saved":len(idx),
        "saved_term_only":len(ok),
        "saved_year_only":len(qa["only_year"]),
        "term_only":ok,
        "shared_year_tree_post_session_count":len(shared_after),
        "shared_year_tree_post_session_examples":shared_after[:30],
        "title_session_date_parse_rejections":len(bad),
        "parse_rejections_examples":bad[:12],
        "origin":"reports/integrated-sync.json + indexes/integrated/meetings.json",
        "interpretation":"All 13 term-only items are post-session committee meetings. This association alone does not establish why the official year tree excludes them.",
    }

def live(report,today="2026-11-02"):
    term=inventory_by_term(today)
    years=inventory_by_year(today)
    _,qa=merge_official_inventories(term,years)
    term_map={str(x["source_id"]):x for x in term}
    year_ids={str(x["source_id"]) for x in years}
    saved_ids={str(x["source_id"]) for x in report["term_only"]}
    live_exception_ids=set(qa["only_term"])
    probe=[]
    for id in IDS:
        source=term_map.get(id)
        detail={
            "source_id":id,
            "present_live_term":source is not None,
            "present_live_year":id in year_ids,
            "live_term_title":source["title"] if source else None,
            "live_term_date":source["date"] if source else None,
            "official_url":SOURCE_PREFIX+id,
        }
        if not source:
            detail["viewer_fetch_status"]="unattempted_no_live_tree_row"
        else:
            try:
                response=fetch(SOURCE_PREFIX+id)
                detail.update({
                    "viewer_fetch_status":"ok",
                    "viewer_html_sha256":hashlib.sha256(response.encode("utf-8")).hexdigest(),
                    "viewer_html_chars":len(response),
                    "viewer_mentions_date":source["date"].replace("-",".") in response or
                        f"{int(source['date'][5:7])}월 {int(source['date'][-2:])}일" in response,
                })
            except Exception as error:
                detail.update({"viewer_fetch_status":"error","viewer_error":type(error).__name__+":"+str(error)[:180]})
        probe.append(detail)
        print(json.dumps({k:detail[k] for k in ("source_id","present_live_term","present_live_year","viewer_fetch_status")},ensure_ascii=False),flush=True)
    unchanged=(live_exception_ids==saved_ids)
    # Full trees are authoritative for *this* live response, but their
    # internal filtering rationale is not externally specified.
    report["live_official_tree_probe"]={
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "term_inventory_rows":len(term),
        "year_inventory_rows":len(years),
        "only_term_ids":sorted(live_exception_ids,key=int),
        "only_year_ids":qa["only_year"],
        "same_13_as_saved_snapshot":unchanged,
        "meeting_details":probe,
        "official_generation_tree_url":"https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsTreeGnrtn.php",
        "official_year_tree_url":"https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsTreeYear.php",
        "source_scope":"direct HTTPS POST tree traversal by existing repository collector; not browser visual inspection",
    }
    if not unchanged:
        report["live_official_tree_probe"]["warning"]="Live inventory differ from earlier snapshot; compare snapshots before updating."
    return report

def run(root=ROOT,do_live=False):
    report=offline(root)
    if do_live:
        live(report)
    report["generated_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
    report["source_files_modified"]=False
    path=root/"reports/integrated-year-term-discrepancy-probe.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "saved_term_only":report["saved_term_only"],
        "shared_year_tree_post_session_count":report["shared_year_tree_post_session_count"],
        "session_title_parse_rejections":report["title_session_date_parse_rejections"],
        "live":report.get("live_official_tree_probe",{}).get("same_13_as_saved_snapshot"),
        "live_term_rows":report.get("live_official_tree_probe",{}).get("term_inventory_rows"),
        "live_year_rows":report.get("live_official_tree_probe",{}).get("year_inventory_rows"),
    },ensure_ascii=False,indent=2))
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--live",action="store_true")
    p.add_argument("--today",default="2026-11-02")
    args=p.parse_args()
    run(do_live=args.live)
