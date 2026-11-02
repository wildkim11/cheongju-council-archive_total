"""Read only two stored official fourth-term session nodes (105,106), macOS.

Sources are exact official node vars from previously verified two-request root
lookup. Two POST calls maximum, no retries; tree metadata only.
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

SOURCE=ROOT/"reports/official-term4-branch-discovery-20261102.json"
OUT=ROOT/"reports/official-term4-target-sessions-20261102.json"

def probe(read=query,out=OUT,sleep=time.sleep):
    if platform.system()!="Darwin":
        raise RuntimeError("macOS read-only test only")
    parent=json.loads(SOURCE.read_text(encoding="utf-8"))
    if parent["status"]!="PASS_TERM4_NODE_DISCOVERED":
        raise RuntimeError("Source session nodes not previously checked")
    sessions={str(n.get("var03")):n for n in parent["term4_children"]}
    required=("105","106")
    if any(k not in sessions or sessions[k].get("var01")!="4" for k in required):
        raise RuntimeError("Expected official session not found in saved root response")
    result={
        "schema":"official-term4-two-session-navigation/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_root_probe":"reports/official-term4-branch-discovery-20261102.json",
        "source_hostname":"councilrec.cheongju.go.kr",
        "runner":"macOS original collector TLS",
        "requests_attempted":0,"request_limit":2,"retries":0,
        "session_children":{},"errors":[],
        "archive_files_modified":False,"production_sync_enabled":False,
        "operational_release_authorized":False,
    }
    for session in required:
        if result["requests_attempted"]:
            sleep(0.35)
        result["requests_attempted"]+=1
        try:
            node=sessions[session]
            rows=read({k:v for k,v in node.items() if k.startswith("var")})
            result["session_children"][session]={
                "count":len(rows),
                "children":[compact(row) for row in rows],
            }
        except Exception as exc:
            result["errors"].append({"session":session,"error_type":type(exc).__name__,
                                      "message":str(exc)[:180]})
            break
    result["status"]="PASS_TWO_SESSIONS_DISCOVERED" if len(result["session_children"])==2 else "INCONCLUSIVE"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result

if __name__=="__main__":
    print(json.dumps(probe(),ensure_ascii=False,indent=2))
