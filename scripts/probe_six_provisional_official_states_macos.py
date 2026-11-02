"""Read-only macOS official states for SIX saved provisional meeting IDs.

Use the previously verified source-derived 105 and 106 session tree branches,
then query exactly four relevant committee nodes, never the rest of the
official archive. No reruns/retries, source edits, full inventory or body fetch.
The old canonical source statuses stay unchanged. This is *candidate discovery*.
"""
from __future__ import annotations

import datetime as dt
import json
import platform
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from probe_term4_branch_shape import query,compact

SOURCE=ROOT/"reports/official-term4-target-sessions-20261102.json"
INDEX=ROOT/"indexes/integrated/initial_term_4.json"
OUT=ROOT/"reports/official-six-provisional-status-20261102.json"
TARGET={
    "4017":("105","C101"),
    "4018":("106","A010"),
    "4019":("106","A010"),
    "4020":("106","C501"),
    "4021":("106","C501"),
    "4022":("106","C403"),
}
STATUS={"Y":"published","N":"provisional"}
LIMIT=4

def compare(saved:dict,live_nodes:list[dict],target:dict[str,tuple[str,str]],session:str,committee:str)->dict:
    """Return only claims supported by the official leaf var12 and var09."""
    actual={}
    duplicates=[]
    for node in live_nodes:
        sid=str(node.get("var12") or "")
        if not sid or not sid.isdigit():
            continue
        if sid in actual:
            duplicates.append(sid)
        actual[sid]=node
    expected=[sid for sid,(ses,code) in target.items() if (ses,code)==(session,committee)]
    results={}
    for sid in expected:
        prior=saved[sid]
        node=actual.get(sid)
        if node is None:
            results[sid]={
                "stored_status":prior["publication_status"],
                "live_status":None,
                "verification":"NOT_LISTED_IN_TARGETED_OFFICIAL_COMMITTEE_BRANCH",
                "warning":"Not evidence of deletion; different branches or future official changes may exist",
            }
            continue
        code=node.get("var09")
        status=STATUS.get(code)
        results[sid]={
            "stored_status":prior["publication_status"],
            "live_status_code":code,
            "live_status":status,
            "verification":"CONFIRMED_LIVE_OFFICIAL_LEAF" if status else "UNKNOWN_OFFICIAL_STATUS_CODE",
            "status_changed":status!=prior["publication_status"] if status else None,
            "title_leaf":str(node.get("text",""))[:210],
            "official_leaf_id":sid,
        }
    return {"session":session,"committee_code":committee,
            "leaf_count":len(actual),
            "listed_source_ids":sorted(actual,key=lambda s:int(s)),
            "duplicate_ids":duplicates,
            "records":results,
            "potential_new_ids_in_targeted_branch":[sid for sid in actual if sid not in saved]}

def run(read=query,out=OUT,sleep=time.sleep):
    if platform.system()!="Darwin":
        raise RuntimeError("Read-only macOS runner required")
    prior=json.loads(INDEX.read_text(encoding="utf-8"))
    saved={str(x["source_id"]):x for x in prior}
    if len(saved)!=50:
        raise RuntimeError("Unrecognized original term4 baseline")
    if any(sid not in saved or saved[sid]["publication_status"]!="provisional" for sid in TARGET):
        raise RuntimeError("Saved six provisional IDs no longer match original baseline")
    snapshot=json.loads(SOURCE.read_text(encoding="utf-8"))
    if snapshot["status"]!="PASS_TWO_SESSIONS_DISCOVERED":
        raise RuntimeError("No verified session branch source")
    groups=sorted(set(TARGET.values()))
    if len(groups)!=LIMIT:
        raise AssertionError("Must query exactly 4 distinct committee subtrees")
    report={
        "schema":"official-six-provisional-targeted-status/1",
        "timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "host":"councilrec.cheongju.go.kr",
        "runner":"GitHub macOS original collector TLS with verified certificate",
        "original_index_count":len(saved),
        "target_source_ids":sorted(TARGET,key=int),
        "max_requests":LIMIT,
        "requests_attempted":0,
        "retries":0,
        "committees":[],
        "errors":[],
        "source_archive_modified":False,
        "production_sync_enabled":False,
        "operational_release_authorized":False,
    }
    for session,committee in groups:
        rows=snapshot["session_children"].get(session,{}).get("children",[])
        candidates=[x for x in rows if x.get("var02")==committee and str(x.get("var03"))==session]
        if len(candidates)!=1:
            report["errors"].append({
                "step":"official_branch_lookup",
                "session":session,"committee":committee,
                "message":"Official saved session tree does not contain exactly one required committee node"
            })
            break
        if report["requests_attempted"]:
            sleep(0.35)
        report["requests_attempted"]+=1
        try:
            node=candidates[0]
            children=read({k:v for k,v in node.items() if k.startswith("var")})
            report["committees"].append(compare(saved,children,TARGET,session,committee))
        except Exception as exc:
            report["errors"].append({
                "step":"official_committee_read",
                "session":session,"committee":committee,
                "exception_type":type(exc).__name__,
                "message":str(exc)[:180],
            })
            break
    records={}
    for group in report["committees"]:
        records.update(group["records"])
    if len(records)!=len(TARGET) or report["errors"]:
        report["status"]="PARTIAL_TARGETED_VERIFICATION"
    elif all(x["verification"]=="CONFIRMED_LIVE_OFFICIAL_LEAF" for x in records.values()):
        report["status"]="PASS_ALL_SIX_OFFICIAL_STATUS_VERIFIED"
    else:
        report["status"]="UNVERIFIED_OFFICIAL_LEAF_MISSING_OR_UNKNOWN"
    report["results_by_id"]=records
    report["confirmed_live_status_count"]=sum(r["verification"]=="CONFIRMED_LIVE_OFFICIAL_LEAF" for r in records.values())
    report["confirmed_status_changed_ids"]=sorted(
        (sid for sid,r in records.items()
         if r["verification"]=="CONFIRMED_LIVE_OFFICIAL_LEAF" and r["status_changed"]),
        key=int
    )
    report["old_snapshot_modified"]=False
    report["methodology_warning"]="Only four specific committee nodes, not all new/current meetings or a full inventory. Absence in a targeted node is not deletion."
    if report["requests_attempted"]>LIMIT:
        raise RuntimeError("NETWORK_BUDGET_EXCEEDED")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    print(json.dumps(run(),ensure_ascii=False,indent=2))
