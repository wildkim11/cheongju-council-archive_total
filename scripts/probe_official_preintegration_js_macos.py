"""Two legacy council navigation JS source probes, original verified TLS, no writing.

The official HTML links to /minuteschj and /minuteschw, not the integrated
/minutes namespace. Verify source code references without guessing endpoints.
At most FOUR bounded GETs; metadata only plus short nearby source snippets.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import http.client
import json
import platform
import re
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_integrated_minutes as collector

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/official-preintegration-js-endpoints-readonly-20261102.json"
HOST="councilrec.cheongju.go.kr"
SOURCES={
 "cheongju_old_city":[
   "/minuteschj/js/svc/svc.mnts.tree.js",
   "/minuteschj/js/svc/svc.mnts.tree.var.js",
 ],
 "cheongwon_old_county":[
   "/minuteschw/js/svc/svc.mnts.tree.js",
   "/minuteschw/js/svc/svc.mnts.tree.var.js",
 ],
}
MAX_REQUESTS=4
MAX_BYTES=300*1024

def get(path):
    if path not in sum(SOURCES.values(),[]):
        raise ValueError("Source not present in official portal HTML")
    c=http.client.HTTPSConnection(HOST,timeout=12,context=collector.TLS)
    try:
        c.request("GET",path,headers={"User-Agent":"CheongjuCouncilArchive/0.1"})
        response=c.getresponse()
        body=response.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:
            raise ValueError("JS exceeds approved size")
        return response.status,body
    finally:
        c.close()

def inspect(path,status,body):
    out={"path":path,"status":status,"bytes":len(body),
         "sha256":hashlib.sha256(body).hexdigest(),
         "candidate_only":True}
    if status!=200:
        out["finding"]="HTTP_NOT_200"
        return out
    code=body.decode("utf-8-sig")
    # Literal source excerpts prove the route names; never treat them as
    # instructions to the runner. Keep bounded excerpts, no executable JS.
    needles=("TreeGnrtn","TreeYear","SvcMnts","svc.mnts",
             "url:","ajax","var10","var11","Viewer","minuteschj","minuteschw")
    spans=[]
    seen=set()
    for needle in needles:
        for match in list(re.finditer(re.escape(needle),code,re.I))[:5]:
            start=max(0,match.start()-95)
            end=min(len(code),match.end()+145)
            snippet=" ".join(code[start:end].split())
            if snippet not in seen:
                spans.append({"keyword":needle,"context":snippet[:250]})
                seen.add(snippet)
    out["source_contexts"]=spans[:32]
    out["literal_php_paths"]=sorted(set(re.findall(
        r"[/A-Za-z0-9._%-]+\.php(?:\?[A-Za-z0-9_=&%.-]+)?",code
    )))[:40]
    out["literal_tree_names"]=sorted(set(re.findall(
        r"(?:Svc|Prev|Prv)[A-Za-z0-9_]*Tree[A-Za-z0-9_]*",code
    )))[:40]
    out["finding"]="JS_SOURCE_READABLE_ENDPOINT_REFERENCE_DISCOVERY"
    return out

def run(read=get,out=OUT,pause=time.sleep):
    if platform.system()!="Darwin":raise RuntimeError("macOS only")
    report={"schema":"official-preintegration-js-source-refs/1",
      "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "requests_attempted":0,"request_limit":MAX_REQUESTS,
      "retries":0,"sources":[],"errors":[],
      "archive_modified":False,"full_legacy_inventory_claimed":False,
      "production_collection_enabled":False}
    for scope,paths in SOURCES.items():
        for path in paths:
            if report["requests_attempted"]:pause(0.35)
            report["requests_attempted"]+=1
            try:
                status,body=read(path)
                report["sources"].append({"scope":scope,**inspect(path,status,body)})
            except Exception as e:
                report["errors"].append({"scope":scope,"path":path,"type":type(e).__name__,"message":str(e)[:150]})
    report["status"]="PASS_FOUR_OFFICIAL_LEGACY_SCRIPTS_READ" if len(report["sources"])==4 and not report["errors"] and all(x["status"]==200 for x in report["sources"]) else "INCONCLUSIVE_LEGACY_SOURCE_SCRIPTS"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report
if __name__=="__main__":print(json.dumps(run(),ensure_ascii=False,indent=2))
