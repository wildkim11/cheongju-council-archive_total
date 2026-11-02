"""GET NO bodies; POST exactly two original verified legacy council term roots.

Two official Javascript files prove these endpoints use POST with
data={"var10":v}; the two official portal pages contain the term navigation
initializer. Query only root generation. No recursion or retries and never
write the original archive or cross-scope IDs.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import http.client
import json
import platform
import sys
import time
import urllib.parse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_integrated_minutes as collector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/official-preintegration-root-trees-readonly-20261102.json"
HOST="councilrec.cheongju.go.kr"
ROOTS={
 "cheongju_old_city":"/minuteschj/svc/web/cms/mnts/SvcMntsTreeGnrtn.php",
 "cheongwon_old_county":"/minuteschw/svc/web/cms/mnts/SvcMntsTreeGnrtn.php",
}
PAYLOAD={"var10":"SvcMntsTreeGnrtn"}
RESPONSE_CAP=2*1024*1024

def read(path):
    if path not in ROOTS.values():
        raise ValueError("Not an official JS-verified source root path")
    c=http.client.HTTPSConnection(HOST,timeout=12,context=collector.TLS)
    try:
        c.request("POST",path,urllib.parse.urlencode(PAYLOAD).encode("utf-8"),
                  headers={"User-Agent":"CheongjuCouncilArchive/0.1",
                           "Content-Type":"application/x-www-form-urlencoded"})
        response=c.getresponse()
        raw=response.read(RESPONSE_CAP+1)
        if len(raw)>RESPONSE_CAP:
            raise ValueError("Root response larger than approved size")
        return response.status,raw
    finally:
        c.close()

def classify(scope,path,status,raw):
    result={
        "scope":scope,
        "url":f"https://{HOST}{path}",
        "http_status":status,
        "response_bytes":len(raw),
        "response_sha256":hashlib.sha256(raw).hexdigest(),
        "root_nodes":[],
        "count":None,
    }
    if status!=200:
        result["verification"]="HTTP_FAILED"
        return result
    try:
        roots=json.loads(raw.decode("utf-8-sig"))
        if not isinstance(roots,list):
            raise ValueError("Non-array official root JSON")
        result["count"]=len(roots)
        result["root_nodes"]=[
          {k:v for k,v in x.items()
           if k in ("text","var01","var02","var03","var04","var09","var10","var11","var12")
           and isinstance(v,(str,int,bool,type(None)))}
          for x in roots if isinstance(x,dict)
        ][:50]
        if len(result["root_nodes"])!=len(roots) or not roots:
            raise ValueError("Invalid official root nodes")
        result["verification"]="PASS_OFFICIAL_LEGACY_SCOPE_TERM_ROOT"
    except Exception as error:
        result["verification"]="JSON_OR_SHAPE_INCONCLUSIVE"
        result["parser_error_type"]=type(error).__name__
        result["parser_error"]=str(error)[:190]
    return result

def probe(read_call=read,pause=time.sleep,out=OUT):
    if platform.system()!="Darwin":
        raise RuntimeError("macOS-only read-only official source probe")
    report={
      "schema":"cheongju-official-preintegration-two-term-roots/1",
      "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "source":"official Javascript verified legacy SvcMntsTreeGnrtn.php",
      "requests_attempted":0,"request_limit":2,"retries":0,
      "root_results":[],"errors":[],
      "archive_source_files_modified":False,
      "full_legacy_inventory_claimed":False,
      "record_bodies_downloaded":0,
      "production_collection_enabled":False,
    }
    for scope,path in ROOTS.items():
        if report["requests_attempted"]:
            pause(0.35)
        report["requests_attempted"]+=1
        try:
            status,raw=read_call(path)
            report["root_results"].append(classify(scope,path,status,raw))
        except Exception as e:
            report["errors"].append({
                "scope":scope,"type":type(e).__name__,
                "reason":str(e)[:160],
            })
    report["status"]=(
        "PASS_BOTH_PREINTEGRATION_TERM_ROOTS"
        if len(report["root_results"])==2 and not report["errors"] and all(
            r["verification"]=="PASS_OFFICIAL_LEGACY_SCOPE_TERM_ROOT"
            for r in report["root_results"])
        else "INCONCLUSIVE_PREINTEGRATION_ROOT_TREES"
    )
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    print(json.dumps(probe(),ensure_ascii=False,indent=2))
