"""Direct, bounded source-tree comparison of all 13 calendar-year rollover minutes.

Read-only and selective. Traverses only official term/year roots, each target
session, and a committee branch when its official source code matches. Never
interprets failed/incomplete queries as proof of absence.
"""
from __future__ import annotations
import collections
import datetime as dt
import json
import re
from pathlib import Path
from audit_official_tree_discrepancy import ROOT, offline
from probe_meeting_tree_bounded import request, slim

OUT="reports/official-year-rollover-13-tree-paths.json"
MAX_REQUESTS=90
cache={}
stats={"requests":0,"hits":0,"failures":0}
failures=[]

def nodes(kind,node):
    key=(kind,json.dumps({k:v for k,v in node.items() if k.startswith("var")},ensure_ascii=False,sort_keys=True))
    if key in cache:
        stats["hits"]+=1
        return cache[key]
    if stats["requests"]>=MAX_REQUESTS:
        raise RuntimeError("Hard request limit reached")
    stats["requests"]+=1
    try:
        raw,seconds=request(kind,node=node)
        rows=json.loads(raw)
        if not isinstance(rows,list):
            raise ValueError("tree node result is not list")
        cache[key]=rows
        return rows
    except Exception as e:
        stats["failures"]+=1
        failures.append({"kind":kind,"node":slim(node),"error":type(e).__name__+":"+str(e)[:160]})
        raise

def find_child(children,target):
    exact=[x for x in children if str(x.get("var01"))==str(target)]
    if len(exact)!=1:
        raise ValueError(f"Expected 1 matching year/term {target}, found {len(exact)}")
    return exact[0]

def get_session_children(kind,root,term_or_year,session_no):
    high=nodes(kind,find_child(root,term_or_year))
    matches=[x for x in high if re.search(rf"제0*{int(session_no)}회(?=\[)",str(x.get("text","")))]
    if len(matches)!=1:
        raise ValueError(f"Official {kind} tree has {len(matches)} session {session_no} under {term_or_year}")
    return matches[0]

def navigate(kind,session_node,case):
    id=case["source_id"]
    code=case["committee_code"]
    target="미세먼지" if code=="G220" else "의회운영위원회"
    steps=[]
    node=session_node
    for depth in range(5):
        children=nodes(kind,node)
        known=[str(x["var12"]) for x in children if x.get("var12")]
        step={"depth":depth,"current":slim(node),"child_count":len(children),
              "leaf_count":len(known),"matched_leaf":id in known}
        steps.append(step)
        if id in known:
            return {"result":"found","source_id":id,"path":steps}
        if any(x.get("var12") for x in children):
            # If this is the fully-enumerated leaf level, a missing ID is
            # supported only for the specific navigated committee branch.
            return {"result":"absent_in_complete_leaf_branch","source_id":id,"path":steps}
        # Exact official committee code takes precedence over substring names:
        # e.g. C101 '의회운영위원회' and J101 '의회운영위원회행정사무감사'
        # must never be treated as two candidate branches.
        opts=[x for x in children if not x.get("var12") and
              str(x.get("var02") or "")==code]
        if not opts:
            opts=[x for x in children if not x.get("var12") and
                  str(x.get("text","")).strip()==target]
        if not opts:
            return {"result":"absent_committee_branch","source_id":id,
                    "committee_code":code,"path":steps,
                    "children_sample":[slim(x) for x in children[:18]]}
        if len(opts)!=1:
            return {"result":"ambiguous_committee_code","source_id":id,
                    "options":len(opts),"path":steps,
                    "children_sample":[slim(x) for x in children[:18]]}
        node=opts[0]
    return {"result":"depth_limit","source_id":id,"path":steps}

def run(root=ROOT):
    report={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "read_only":True,"timeout_per_request_seconds":7,
            "request_limit":MAX_REQUESTS,
            "method":"official term/year root -> exact session -> matching committee -> leaf",
            "cases":[],"failure_log":failures}
    case_rows=offline(root)["term_only"]
    roots={
        "Year":nodes("Year",{"var10":"SvcMntsTreeYearGnrtn"}),
        "Gnrtn":nodes("Gnrtn",{"var10":"SvcMntsTreeGnrtn"}),
    }
    for case in case_rows:
        num=re.search(r"제(\d+)회\[",case["title"])
        if not num:
            raise ValueError("No session number in title for "+case["source_id"])
        record={
           "source_id":case["source_id"],"meeting_date":case["meeting_date"],
           "session_end":case["session_end"],"session_no":int(num[1]),
           "term":case["term"],"committee_code":case["committee_code"],
           "official_url":case["official_url"],
           "paths":{},
        }
        for kind in ("Year","Gnrtn"):
            parent_year=case["session_end"][:4] if kind=="Year" else case["term"]
            try:
                session=get_session_children(kind,roots[kind],parent_year,record["session_no"])
                record["paths"][kind]=navigate(kind,session,case)
                record["paths"][kind]["session"]=slim(session)
            except Exception as e:
                record["paths"][kind]={"result":"unverified_source_request",
                    "error":type(e).__name__+":"+str(e)[:180]}
        report["cases"].append(record)
        print(json.dumps({"id":record["source_id"],"year":record["paths"]["Year"]["result"],
                          "term":record["paths"]["Gnrtn"]["result"]},ensure_ascii=False),flush=True)
    report["request_stats"]=stats
    counts={}
    for kind in ("Year","Gnrtn"):
        counts[kind]=dict(collections.Counter(x["paths"][kind]["result"] for x in report["cases"]))
    report["summary"]=counts
    report["interpretation"]="Only complete leaf-branch traversals establish branch-specific nonappearance. Requests that fail or cannot uniquely select the committee branch are inconclusive."
    p=root/OUT
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"summary":counts,"request_stats":stats,"path":OUT},ensure_ascii=False),flush=True)
    return report

if __name__=="__main__":
    run()
