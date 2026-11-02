"""Read-only macOS official root + term 4 immediate children discovery.

Exactly two maximum tree requests, zero retries, no recursion, no existing archive
or export mutation; original collector TLS ciphers and verified certificates.
The captured node var-fields are official navigation metadata only, not bodies.
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
import collect_integrated_minutes as c

HOST="councilrec.cheongju.go.kr"
TREE="/minutes/svc/web/cms/mnts/SvcMntsTreeGnrtn.php"
OUT=ROOT/"reports/official-term4-branch-discovery-20261102.json"

def query(payload:dict)->list[dict]:
    if not payload or any(not k.startswith("var") for k in payload):
        raise ValueError("Only discovered original official generation tree node variables permitted")
    raw=urllib.parse.urlencode(payload).encode("utf-8")
    conn=http.client.HTTPSConnection(HOST,timeout=12,context=c.TLS)
    try:
        conn.request("POST",TREE,raw,headers={
            "User-Agent":"CheongjuCouncilArchive/0.1",
            "Content-Type":"application/x-www-form-urlencoded",
        })
        response=conn.getresponse()
        data=response.read(2*1024*1024+1)
        if response.status!=200:
            raise ValueError("Official tree non-200 "+str(response.status))
        if len(data)>2*1024*1024:
            raise ValueError("Tree response oversized")
        rows=json.loads(data.decode("utf-8-sig"))
        if not isinstance(rows,list) or not all(isinstance(row,dict) for row in rows):
            raise ValueError("Unexpected tree node JSON")
        return rows
    finally:
        conn.close()

def compact(node):
    return {k:v for k,v in node.items()
            if (k.startswith("var") or k=="text")
            and isinstance(v,(str,int,bool,type(None)))}

def probe(read=query,out=OUT,sleep=time.sleep):
    if platform.system()!="Darwin":
        raise RuntimeError("Expected GitHub macOS runner")
    report={
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "schema":"official-term4-immediate-navigation-shape/1",
        "runner":"macOS original collector verified TLS",
        "official_host":HOST,
        "max_requests":2,
        "requests_attempted":0,
        "retries":0,
        "source_archive_modified":False,
        "production_collection_enabled":False,
        "operational_release_authorized":False,
        "root_count":None,
        "term4_child_count":None,
        "term4_children":[],
        "errors":[],
    }
    try:
        report["requests_attempted"]+=1
        root=read({"var10":"SvcMntsTreeGnrtn"})
        report["root_count"]=len(root)
        selected=[x for x in root if str(x.get("var01"))=="4"]
        if len(selected)!=1:raise ValueError("Need exactly one term4 root")
        report["term4_root"]=compact(selected[0])
        sleep(0.35)
        report["requests_attempted"]+=1
        children=read({k:v for k,v in selected[0].items() if k.startswith("var")})
        report["term4_child_count"]=len(children)
        report["term4_children"]=[compact(x) for x in children]
        report["status"]="PASS_TERM4_NODE_DISCOVERED"
    except Exception as exc:
        report["errors"].append({"error_type":type(exc).__name__,"message":str(exc)[:180]})
        report["status"]="INCONCLUSIVE"
    if report["requests_attempted"]>2:
        raise RuntimeError("Request cap exceeded")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    print(json.dumps(probe(),ensure_ascii=False,indent=2))
