"""Two bounded macOS original-TLS official reads: provisional 4019 + root tree.

Uses EXACT original collector TLS configuration with certificate validation.
No retry; stop if first request fails; no recursive inventory, no archived writes.
A changed live body is a review candidate, NOT auto-updated canonical evidence.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import http.client
import json
import platform
import sys
import urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import collect_integrated_minutes as c
import probe_official_readonly_limited as p

HOST="councilrec.cheongju.go.kr"
TREE="/minutes/svc/web/cms/mnts/SvcMntsTreeGnrtn.php"
VIEWER="/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=4019"
OUTPUT=ROOT/"reports/official-macos-original-tls-4019-tree-20261102.json"
CAP=12*1024*1024

def original_tls_read(method,target,params=None):
    if (method,target)!=( "GET",VIEWER) and (method,target)!=("POST",TREE):
        raise ValueError("Read-only allowlist forbids this path")
    if method=="POST" and params!={"var10":"SvcMntsTreeGnrtn"}:
        raise ValueError("Non-root query forbidden")
    body=None if params is None else urllib.parse.urlencode(params).encode("ascii")
    conn=http.client.HTTPSConnection(HOST,timeout=12,context=c.TLS)
    try:
        conn.request(method,target,body,headers={
            "User-Agent":"CheongjuCouncilArchive/0.1",
            "Content-Type":"application/x-www-form-urlencoded",
        })
        response=conn.getresponse()
        data=response.read(CAP+1)
        if len(data)>CAP:
            raise RuntimeError("RESPONSE_EXCEEDS_12_MIB")
        if response.status!=200:
            raise RuntimeError("OFFICIAL_NON_200_HTTP_"+str(response.status))
        return {"http_status":response.status,
                "response_bytes":len(data),
                "response_sha256":hashlib.sha256(data).hexdigest(),
                "text":data.decode("utf-8-sig")}
    finally:
        conn.close()

def probe(request_func=original_tls_read,out=OUTPUT):
    if platform.system()!="Darwin":
        raise RuntimeError("MACOS_ONLY_OFFICIAL_READONLY")
    records=json.loads((ROOT/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
    if len(records)!=2339:
        raise RuntimeError("ARCHIVE_BASELINE_CHANGED")
    prior=next(r for r in records if str(r.get("source_id"))=="4019")
    if prior["publication_status"]!="provisional":
        raise RuntimeError("Unexpected archived status for provisional case")
    result={
        "schema":"official-macos-original-tls-provisional-and-tree/1",
        "timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "runner":"GitHub hosted macOS",
        "scope":"known provisional 4019 viewer + generation tree root only",
        "tls_context":"identical to original collector (TLSv1.2 minimum, DEFAULT ciphers, verified)",
        "request_cap":2,
        "attempts":0,
        "retries":0,
        "samples":[],
        "tree":None,
        "errors":[],
        "source_archive_modified":False,
        "production_collection_enabled":False,
        "operational_release_authorized":False,
    }
    for method,target,params in (("GET",VIEWER,None),
                                  ("POST",TREE,{"var10":"SvcMntsTreeGnrtn"})):
        result["attempts"]+=1
        try:
            response=request_func(method,target,params)
            if method=="GET":
                result["samples"].append(p.compare_viewer(prior,response))
            else:
                result["tree"]=p.parse_root_tree(response)
        except Exception as exc:
            result["errors"].append({
                "step":"viewer_4019" if method=="GET" else "generation_tree_root",
                "error_type":type(exc).__name__,
                "error":str(exc)[:180],
            })
            break
    if result["errors"]:
        result["status"]="PARTIAL_OR_INCONCLUSIVE_NETWORK"
    elif result["tree"] and result["tree"].get("integrated_terms_1_to_4_present"):
        if result["samples"][0]["comparison"]=="SAME_SAVED_BODY":
            result["status"]="PASS_4019_BODY_MATCH_AND_TREE_ROOT"
        else:
            result["status"]="PASS_CONNECTIVITY_BUT_4019_BODY_NEEDS_REVIEW"
    else:
        result["status"]="INCONCLUSIVE_TREE_ROOT"
    if result["attempts"]>2:
        raise RuntimeError("REQUEST_CAP_BREACHED")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return result

if __name__=="__main__":
    print(json.dumps(probe(),indent=2,ensure_ascii=False))
