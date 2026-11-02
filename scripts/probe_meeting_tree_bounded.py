"""Bounded read-only probe of official Cheongju Council minute tree branch metadata.

No archive/index/export file is modified. Unlike inventory_by_term/year(), this
probe never traverses every tree node and never retries a timeout. The report
includes failures rather than treating them as missing source records.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import json
import ssl
import time
import urllib.parse
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE="https://councilrec.cheongju.go.kr"
OUT=ROOT/"reports"/"official-tree-bounded-probe-20261102.json"
IDS={"180":"2015-01-23","1848":"2020-01-16","3652":"2025-02-06"}
TIMEOUT=7.0

def request(kind, node=None, viewer_id=None):
    """Single https request, no retry, short socket timeout, restricted host."""
    start=time.monotonic()
    path=(f"/minutes/svc/web/cms/mnts/SvcMntsTree{kind}.php"
          if not viewer_id else
          f"/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn={viewer_id}")
    payload=(urllib.parse.urlencode({k:v for k,v in (node or {}).items()
                        if k.startswith("var")}).encode() if node is not None else None)
    sslctx=ssl.create_default_context()
    sslctx.minimum_version=ssl.TLSVersion.TLSv1_2
    conn=http.client.HTTPSConnection("councilrec.cheongju.go.kr",timeout=TIMEOUT,context=sslctx)
    try:
        conn.request("POST" if payload is not None else "GET",path,
            body=payload,headers={"User-Agent":"CheongjuCouncilArchive-BoundedQA/0.1",
                                   "Content-Type":"application/x-www-form-urlencoded"})
        resp=conn.getresponse()
        blob=resp.read(3_000_000)
        if resp.status !=200:
            raise ValueError(f"HTTP {resp.status}")
        return blob.decode("utf-8-sig"),round(time.monotonic()-start,3)
    finally:
        conn.close()

def slim(node):
    return {key:node.get(key) for key in ("text","var01","var02","var09","var10","var12")
            if key in node}

def mk_node_report(kind,label,node,report):
    entry={"tree":kind,"label":label,"request":{k:node[k] for k in node if k.startswith("var")}}
    try:
        raw,sec=request(kind,node=node)
        rows=json.loads(raw)
        if not isinstance(rows,list):raise ValueError("Root or branch response is not array")
        entry.update({"result":"ok","seconds":sec,"row_count":len(rows),
            "rows_head":[slim(x) for x in rows[:40]],
            "leaf_source_ids":[str(x["var12"]) for x in rows if x.get("var12")]})
    except Exception as error:
        entry.update({"result":"error","error_type":type(error).__name__,
                      "error_detail":str(error)[:220]})
        rows=[]
    report["trees"].append(entry)
    print(json.dumps({"tree":kind,"label":label,"result":entry["result"],
                      "count":entry.get("row_count"),
                      "error":entry.get("error_type")},ensure_ascii=False),flush=True)
    return rows

def run(root=ROOT):
    report={"checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope":"bounded official HTTPS requests; single attempt, seven-second timeout",
        "source_files_modified":False,
        "trees":[],"viewers":[],"findings":[]}
    roots={}
    for kind,key in [("Year","SvcMntsTreeYearGnrtn"),("Gnrtn","SvcMntsTreeGnrtn")]:
        roots[kind]=mk_node_report(kind,"root",{"var10":key},report)
    for kind,targets in [("Year",{"2015","2020","2025"}),
                         ("Gnrtn",{"1","2","3"})]:
        for x in roots[kind]:
            if str(x.get("var01")) not in targets:
                continue
            label=f"root-child-{x.get('var01')}"
            mk_node_report(kind,label,x,report)
    for id,date in IDS.items():
        entry={"source_id":id,"snapshot_date":date,
               "official_url":BASE+"/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="+id}
        try:
            raw,sec=request("Viewer",viewer_id=id)
            entry.update({"result":"ok","seconds":sec,
                        "html_chars":len(raw),
                        "html_sha256":hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                        "official_body_marker_seen": "회의록내용" in raw or "minutesContent" in raw,
                        "date_text_seen":date.replace("-",".") in raw})
        except Exception as e:
            entry.update({"result":"error","error_type":type(e).__name__,
                          "error_detail":str(e)[:220]})
        print(json.dumps({"viewer":id,"result":entry["result"],
                          "error":entry.get("error_type")},ensure_ascii=False),flush=True)
        report["viewers"].append(entry)
    report["findings"].extend([
       "Live nonappearance cannot be concluded when official endpoint is unreachable.",
       "A post-session meeting date is not sufficient to explain the 13 exclusions: 108 post-session meetings were shared by both trees in the stored snapshot.",
       "Response samples diagnose tree schema and endpoint reachability; they do not replace a complete live inventory."
    ])
    out=root/"reports"/OUT.name
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"tree_responses_ok":sum(t["result"]=="ok" for t in report["trees"]),
         "viewer_responses_ok":sum(t["result"]=="ok" for t in report["viewers"]),
         "report":str(out)},ensure_ascii=False),flush=True)
    return report

if __name__=="__main__":
    run()
