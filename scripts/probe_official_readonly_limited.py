"""Bounded, read-only official Cheongju minutes source probe.

NOT a collector. No run_sync, no archive writes, no GitHub main writes.
At most 3 sequential official HTTPS requests, zero retries, at most 12s
per request, 1s quiet interval. Probe stops after the first network error.
The root tree endpoint uses an application/x-www-form-urlencoded POST solely
to query its READ-ONLY tree API (never a submission/update endpoint).

Snapshot comparison is diagnostic only: it does not promote, reclassify,
or overwrite previously archived official source records.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import http.client
import json
import ssl
import sys
import time
import urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import collect_integrated_minutes as c

HOST="councilrec.cheongju.go.kr"
TREE="/minutes/svc/web/cms/mnts/SvcMntsTreeGnrtn.php"
VIEWER="/minutes/svc/web/cms/mnts/SvcMntsViewer.php"
IDS=("3999","4019") # a 2026 published and provisional archived snapshot
MAX_REQUESTS=3
TIMEOUT_SECONDS=12
MAX_RESPONSE_BYTES=12*1024*1024
OUTPUT=ROOT/"reports/official-limited-readonly-probe-20261102.json"


def official_request(method:str,target:str,params:dict|None=None)->dict:
    if method not in ("GET","POST") or not target.startswith("/minutes/svc/web/cms/mnts/"):
        raise ValueError("Refusing non-official read-only endpoint")
    if method=="POST" and (target!=TREE or params!={"var10":"SvcMntsTreeGnrtn"}):
        raise ValueError("Refusing non-root or non-read-only POST")
    if method=="GET" and (not target.startswith(VIEWER+"?schSn=") or not target.split("schSn=",1)[-1].isdigit()):
        raise ValueError("Refusing arbitrary GET target")
    context=ssl.create_default_context()
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    payload=urllib.parse.urlencode(params).encode("ascii") if params else None
    conn=http.client.HTTPSConnection(HOST,timeout=TIMEOUT_SECONDS,context=context)
    try:
        conn.request(method,target,body=payload,headers={
            "User-Agent":"CheongjuCouncilArchive-ReadOnly-Validation/0.1",
            "Accept":"text/html,application/json",
            "Content-Type":"application/x-www-form-urlencoded",
        })
        response=conn.getresponse()
        raw=response.read(MAX_RESPONSE_BYTES+1)
        if len(raw)>MAX_RESPONSE_BYTES:
            raise ValueError("Official response exceeds read-only probe size cap")
        if response.status!=200:
            raise ValueError(f"Official HTTP status {response.status}")
        return {
            "http_status":response.status,
            "response_bytes":len(raw),
            "response_sha256":hashlib.sha256(raw).hexdigest(),
            "text":raw.decode("utf-8-sig"),
        }
    finally:
        conn.close()


def compare_viewer(record:dict,response:dict)->dict:
    evidence={
        "source_id":str(record["source_id"]),
        "stored_date":record["date"],
        "stored_term":record["term"],
        "stored_publication_status":record["publication_status"],
        "stored_body_sha256":record["content_sha256"],
        "http_status":response["http_status"],
        "response_bytes":response["response_bytes"],
        "raw_response_sha256":response["response_sha256"],
    }
    try:
        live_body=c.extract_minutes_body(response["text"])
        live_hash=hashlib.sha256(c.canonical(live_body).encode("utf-8")).hexdigest()
        evidence["body_parsed"]=True
        evidence["live_body_sha256"]=live_hash
        evidence["comparison"]=(
            "SAME_SAVED_BODY" if live_hash==record["content_sha256"]
            else "DIFFERS_FROM_SAVED_BODY_MANUAL_REVIEW"
        )
    except Exception as exc:
        evidence["body_parsed"]=False
        evidence["comparison"]="PARSER_FAILED_MANUAL_REVIEW"
        evidence["parse_error"]=type(exc).__name__+": "+str(exc)[:180]
    return evidence


def parse_root_tree(response:dict)->dict:
    result={
        "http_status":response["http_status"],
        "response_bytes":response["response_bytes"],
        "raw_response_sha256":response["response_sha256"],
    }
    try:
        nodes=json.loads(response["text"])
        if not isinstance(nodes,list):
            raise ValueError("Root tree not JSON list")
        terms=sorted(set(int(n["var01"]) for n in nodes
                         if isinstance(n,dict) and str(n.get("var01","")).isdigit()))
        result.update({
            "parsed":True,
            "root_nodes":len(nodes),
            "declared_numeric_roots":terms,
            "integrated_terms_1_to_4_present":all(x in terms for x in range(1,5)),
        })
    except Exception as exc:
        result.update({"parsed":False,"parse_error":type(exc).__name__+": "+str(exc)[:180]})
    return result


def probe(request_func=official_request, output:Path=OUTPUT, sleep=time.sleep)->dict:
    # Only archived *local* rows can be used for baseline expectations.
    rows=json.loads((ROOT/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
    by_id={str(x["source_id"]):x for x in rows}
    if len(rows)!=2339 or any(k not in by_id for k in IDS):
        raise RuntimeError("Saved 2339 meeting-index baseline changed; probe refused")
    if by_id["3999"]["publication_status"]!="published" or by_id["4019"]["publication_status"]!="provisional":
        raise RuntimeError("Official sample expectation changed; probe refused")
    report={
        "schema":"cheongju-official-readonly-limited-probe/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "policy":{
            "official_hostname":HOST,"max_requests":MAX_REQUESTS,
            "attempts_per_request":1,"timeout_per_request_seconds":TIMEOUT_SECONDS,
            "max_response_bytes":MAX_RESPONSE_BYTES,
            "minimum_seconds_between_successful_requests":1,
            "methods":"GET two known viewer pages; POST root generation-tree read endpoint only",
            "no_recursive_tree":True,"no_body_or_html_saved":True,
            "no_source_writes":True,
        },
        "baseline":{"saved_index_rows":len(rows),"selected_official_source_ids":list(IDS)},
        "requests_attempted":0,"requests_succeeded":0,
        "samples":[],"tree_root":None,"errors":[],
        "source_archive_modified":False,"production_sync_used":False,
        "automatic_collection_enabled":False,
    }
    tasks=[
        ("GET",VIEWER+"?schSn=3999",None,"3999"),
        ("GET",VIEWER+"?schSn=4019",None,"4019"),
        ("POST",TREE,{"var10":"SvcMntsTreeGnrtn"},None),
    ]
    for method,target,payload,source_id in tasks:
        if report["requests_attempted"]:
            sleep(1)
        report["requests_attempted"]+=1
        try:
            data=request_func(method,target,payload)
            report["requests_succeeded"]+=1
            if source_id:
                report["samples"].append(compare_viewer(by_id[source_id],data))
            else:
                report["tree_root"]=parse_root_tree(data)
        except Exception as exc:
            report["errors"].append({
                "request_number":report["requests_attempted"],
                "method":method,
                "endpoint_type":"viewer" if source_id else "term_root_tree",
                "exception_type":type(exc).__name__,
                "message":str(exc)[:220],
            })
            break # No retries and no further requests after first failure.
    if report["errors"]:
        report["status"]="INCONCLUSIVE_SOURCE_UNAVAILABLE"
    elif all(x["comparison"]=="SAME_SAVED_BODY" for x in report["samples"]) and (
        report["tree_root"] and report["tree_root"].get("integrated_terms_1_to_4_present")
    ):
        report["status"]="PASS_LIMITED_LIVE_SOURCE_MATCH"
    else:
        report["status"]="LIVE_RESPONDED_MANUAL_REVIEW_REQUIRED"
    report["successful_body_parses"]=sum(x.get("body_parsed",False) for x in report["samples"])
    report["body_hash_matches"]=sum(x.get("comparison")=="SAME_SAVED_BODY" for x in report["samples"])
    report["operational_release_authorized"]=False
    report["warning"]="This is NOT a full official meeting inventory or approval for archival updates."
    if report["requests_attempted"]>MAX_REQUESTS:
        raise RuntimeError("Internal request cap breached")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    print(json.dumps(probe(),ensure_ascii=False,indent=2))
