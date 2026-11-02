"""Discover official legacy meeting leaf click/viewer from exact portal-linked JS.

GET only each council's referenced async tree plugin and store bounded source
route excerpts; do not store executable JS, parse private data or modify
historical archive records. A raw N tree status remains UNKNOWN until verified
against legacy viewer semantics.
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
import collect_integrated_minutes as c
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/official-preintegration-viewer-js-readonly-20261102.json"
SOURCES={
"cheongju_old_city":"/minuteschj/js/svc/tree/jquery.treeview.async.svc.mnts.js?ver=1.0.2",
"cheongwon_old_county":"/minuteschw/js/svc/tree/jquery.treeview.async.svc.mnts.js?ver=1.0.2",
}
HOST="councilrec.cheongju.go.kr"
LIMIT=2
CAP=512*1024

def get(path):
    if path not in SOURCES.values():raise ValueError("Path not from verified legacy official HTML")
    co=http.client.HTTPSConnection(HOST,timeout=12,context=c.TLS)
    try:
        co.request("GET",path,headers={"User-Agent":"CheongjuCouncilArchive/0.1"})
        response=co.getresponse()
        raw=response.read(CAP+1)
        if len(raw)>CAP:raise ValueError("Unexpected large legacy JS file")
        return response.status,raw
    finally:co.close()

def interpret(scope,status,raw):
    result={"scope":scope,"http_status":status,"bytes":len(raw),
            "sha256":hashlib.sha256(raw).hexdigest(),
            "viewer_reference_confirmed":False}
    if status!=200:return result
    js=raw.decode("utf-8-sig")
    result["script_references"]=sorted(set(re.findall(
        r"/minutes(?:chj|chw)/[a-zA-Z0-9_./?=%&-]+",js
    )))[:30]
    result["php_references"]=sorted(set(re.findall(
        r"[A-Za-z0-9_./-]+\.php",js
    )))[:30]
    contexts=[]
    for needle in ["Viewer","schSn","var12","click","href","window.open","open(",
                   "goMnts","setvar","mousedown","anchor","node.attr","url"]:
        for hit in list(re.finditer(re.escape(needle),js,re.I))[:6]:
            fragment=" ".join(js[max(0,hit.start()-90):hit.end()+150].split())
            contexts.append({"marker":needle,"evidence":fragment[:255]})
    result["source_contexts"]=contexts[:40]
    result["viewer_reference_confirmed"]=any("Viewer.php" in x for x in result["php_references"])
    return result

def run(read=get,out=OUT,pause=time.sleep):
    if platform.system()!="Darwin":raise RuntimeError("macOS required")
    report={"schema":"official-premerger-viewer-click-js-metadata/1",
      "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "requests_attempted":0,"request_cap":LIMIT,"retries":0,
      "sources":[],"errors":[],"archive_modified":False,
      "existing_minutes_saved":0,"prod_sync_enabled":False}
    for scope,path in SOURCES.items():
        if report["requests_attempted"]:pause(0.35)
        report["requests_attempted"]+=1
        try:
            status,raw=read(path)
            report["sources"].append(interpret(scope,status,raw))
        except Exception as error:
            report["errors"].append({"scope":scope,"type":type(error).__name__,"reason":str(error)[:190]})
    report["status"]="PASS_TWO_OFFICIAL_VIEWER_CLICK_JS_READ" if len(report["sources"])==2 and not report["errors"] and all(x["http_status"]==200 for x in report["sources"]) else "INCONCLUSIVE_LEGACY_VIEWER_JS"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report
if __name__=="__main__":print(json.dumps(run(),ensure_ascii=False,indent=2))
