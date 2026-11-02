"""Bounded read-only official YEAR 2026 list check for already verified new IDs.

Only official Year generation tree root and the 2026 subtree are queried.
Stop once ALL THREE schSn=4024, 4025, and 4026 are discovered, otherwise report unknown.
No retries, no source mutation, no access beyond 2026. All navigation vars
derive from the server's own parent node. Exact original secure TLS settings.
"""
from __future__ import annotations

import datetime as dt
import http.client
import json
import platform
import sys
import time
import urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import collect_integrated_minutes as original

HOST="councilrec.cheongju.go.kr"
TARGET="/minutes/svc/web/cms/mnts/SvcMntsTreeYear.php"
OUT=ROOT/"reports/official-year2026-three-new-ids-presence-20261102.json"
IDS={"4024","4025","4026"}
LIMIT=75
WAIT=0.35


def read_tree(params):
    if not params or any(not k.startswith("var") for k in params):
        raise ValueError("Only original server-issued tree node parameters permitted")
    body=urllib.parse.urlencode(params).encode("utf-8")
    conn=http.client.HTTPSConnection(HOST,timeout=12,context=original.TLS)
    try:
        conn.request("POST",TARGET,body,{
            "User-Agent":"CheongjuCouncilArchive/0.1",
            "Content-Type":"application/x-www-form-urlencoded",
        })
        response=conn.getresponse()
        raw=response.read(2*1024*1024+1)
        if response.status!=200 or len(raw)>2*1024*1024:
            raise ValueError("Non-200 or oversized official year tree")
        nodes=json.loads(raw.decode("utf-8-sig"))
        if not isinstance(nodes,list) or not all(isinstance(x,dict) for x in nodes):
            raise ValueError("Invalid official year nodes")
        return nodes
    finally:
        conn.close()


def run(read=read_tree,sleep=time.sleep,out=OUT):
    if platform.system()!="Darwin":
        raise RuntimeError("Expected read-only macOS runner")
    proof={
        "schema":"cheongju-official-year2026-new-id-presence/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "host":HOST,
        "requested_source_ids":sorted(IDS),
        "request_limit":LIMIT,
        "requests_attempted":0,
        "retries":0,
        "year_branch":"2026 only",
        "found":{},
        "errors":[],
        "source_archive_modified":False,
        "production_collection_enabled":False,
        "operational_release_authorized":False,
    }
    seen=set()
    def call(node):
        if proof["requests_attempted"]>=LIMIT:
            raise RuntimeError("OFFICIAL_YEAR_TREE_REQUEST_CAP_REACHED")
        if proof["requests_attempted"]:
            sleep(WAIT)
        proof["requests_attempted"]+=1
        return read(node)
    def visit(node,depth=0):
        if depth>7:
            raise ValueError("unexpected year tree depth")
        signature=tuple(sorted((k,str(v)) for k,v in node.items() if k.startswith("var")))
        if signature in seen:
            raise ValueError("Repeated official year-tree navigation node")
        seen.add(signature)
        children=call({k:v for k,v in node.items() if k.startswith("var")})
        for x in children:
            sid=str(x.get("var12") or "")
            if sid and sid.isdigit():
                if sid in IDS:
                    proof["found"][sid]={
                        "year":"2026",
                        "official_status_code":x.get("var09"),
                        "source_id":sid,
                        "leaf_text":str(x.get("text") or "")[:180],
                    }
            else:
                if len(proof["found"])==len(IDS):
                    return
                visit(x,depth+1)
        return
    try:
        roots=call({"var10":"SvcMntsTreeYearGnrtn"})
        year=[x for x in roots if str(x.get("var01"))=="2026"]
        if len(year)!=1:
            raise ValueError("Expected one official year 2026 root")
        visit(year[0])
    except Exception as exc:
        proof["errors"].append({"type":type(exc).__name__,"message":str(exc)[:200]})
    proof["three_new_ids_confirmed_in_official_year2026"]=set(proof["found"])==IDS
    proof["three_new_ids_confirmed_in_official_year2026"] = (
        proof["three_new_ids_confirmed_in_official_year2026"]
        and all(proof["found"][sid].get("official_status_code")=="N" for sid in IDS)
    )
    proof["status"]=(
        "PASS_THREE_NEW_IDS_IN_OFFICIAL_YEAR2026"
        if proof["three_new_ids_confirmed_in_official_year2026"]
        else "INCONCLUSIVE_YEAR2026_SOURCE_MEMBERSHIP"
    )
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(proof,ensure_ascii=False,indent=2))
    return proof

if __name__=="__main__":
    run()
