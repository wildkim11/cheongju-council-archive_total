"""One-time original-TLS verified discovery of TWO official PRE-2014 minutes portals.

Only GET the two exact URLs linked by the present Cheongju Council official
minutes homepage. No list crawl, no archive modification, no original body
acquisition, no redirects to other hosts, no repeated requests.
Store hash + parsed HTML structure metadata, not raw HTML/source contents.
The iframe/JS API paths are DISCOVERY CANDIDATES until separately verified.
"""
from __future__ import annotations
import datetime as dt
import hashlib
from html.parser import HTMLParser
import http.client
import json
import platform
import re
from pathlib import Path
import sys
import time
import urllib.parse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import collect_integrated_minutes as original

HOST="councilrec.cheongju.go.kr"
PAGES={
  "cheongju_old_city":"/content/cityMinutes/prevsession.html",
  "cheongwon_old_county":"/content/gunMinutes/prevsession.html",
}
OUT=ROOT/"reports/official-preintegration-portals-readonly-20261102.json"
MAX_BODY=3*1024*1024

class MarkupShape(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title=False
        self.title_text=[]
        self.iframes=[]
        self.scripts=[]
        self.forms=[]
        self.frames=[]
        self.selects=[]
        self.textareas=[]
        self.portal_links=[]
        self.inline_text=[]
        self.capture_text=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="title":
            self.title=True
        if tag=="iframe":
            self.iframes.append({k:a.get(k) for k in ("src","id","name") if a.get(k)})
        if tag=="frame":
            self.frames.append({k:a.get(k) for k in ("src","name") if a.get(k)})
        if tag=="script" and a.get("src"):
            self.scripts.append(a["src"])
        if tag=="form":
            self.forms.append({k:a.get(k) for k in ("action","method","id") if a.get(k)})
        if tag=="select":
            self.selects.append({k:a.get(k) for k in ("id","name") if a.get(k)})
        if tag=="textarea":
            self.textareas.append({k:a.get(k) for k in ("id","name") if a.get(k)})
        if tag=="a":
            href=a.get("href","")
            if any(x in href.lower() for x in ("prevsession","cityminutes","gunminutes","/minutes/","viewer")):
                if len(self.portal_links)<50:
                    self.portal_links.append(href[:250])
    def handle_endtag(self,tag):
        if tag=="title":
            self.title=False
    def handle_data(self,data):
        if self.title:
            self.title_text.append(data.strip())

def read_portal(relative):
    if relative not in PAGES.values():
        raise ValueError("Unauthorized portal path")
    conn=http.client.HTTPSConnection(HOST,timeout=12,context=original.TLS)
    try:
        conn.request("GET",relative,headers={"User-Agent":"CheongjuCouncilArchive/0.1"})
        resp=conn.getresponse()
        raw=resp.read(MAX_BODY+1)
        if len(raw)>MAX_BODY:
            raise ValueError("Portal HTML exceeds safety cap")
        return resp.status,resp.getheader("Content-Type"),resp.getheader("Location"),raw
    finally:
        conn.close()

def examine(scope,path,status,content_type,location,raw):
    result={
        "council_scope":scope,
        "official_url":f"https://{HOST}{path}",
        "status":status,
        "mime_type":content_type,
        "redirection_location":location,
        "response_bytes":len(raw),
        "html_sha256":hashlib.sha256(raw).hexdigest(),
        "parse_ok":False,
        "verified_minutes_records":0,
        "archive_records_written":0,
    }
    if status!=200:
        result["finding"]="HTTP_NON_200_REQUIRES_SOURCE_RECHECK"
        return result
    try:
        text=raw.decode("utf-8-sig")
        parser=MarkupShape()
        parser.feed(text)
        result.update({
            "parse_ok":True,
            "title":" ".join(parser.title_text)[:250],
            "iframe_nodes":parser.iframes[:15],
            "frame_nodes":parser.frames[:15],
            "external_scripts":parser.scripts[:30],
            "forms":parser.forms[:15],
            "selects":parser.selects[:25],
            "textareas":parser.textareas[:25],
            "candidate_portal_links":parser.portal_links[:50],
            "legacy_svc_paths_sorted":sorted(set(re.findall(
                r"(?:(?:/minutes)?/svc/[A-Za-z0-9_./?=&%-]+)",
                text,flags=re.I
            )))[:30],
            "html_structure_marker_counts":{
                term:len(re.findall(re.escape(term),text,flags=re.I))
                for term in (
                    "iframe","SvcMnts","PrevMnts","prevsession","gunMinutes",
                    "cityMinutes","var10","var01","schSn","회의록",
                )
            },
            "finding":"HTML_STRUCTURE_READABLE_NOT_YET_MINUTES_BODY",
        })
    except Exception as error:
        result["finding"]="HTML_PARSE_INCONCLUSIVE"
        result["parse_error_type"]=type(error).__name__
        result["parse_error"]=str(error)[:160]
    return result

def probe(read=read_portal,pause=time.sleep,out=OUT):
    if platform.system()!="Darwin":
        raise RuntimeError("Original-TLS official portal QA macOS-only")
    report={
        "schema":"cheongju-preintegration-two-official-minutes-portal-probe/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "linked_from":"https://councilrec.cheongju.go.kr/",
        "source":"official Cheongju Council councilrec host",
        "request_limit":2,
        "requests_attempted":0,
        "retries":0,
        "official_gets":[],
        "errors":[],
        "archive_minutes_modified":False,
        "production_source_sync_enabled":False,
        "operational_release_authorized":False,
    }
    for scope,path in PAGES.items():
        if report["requests_attempted"]:
            pause(0.35)
        report["requests_attempted"]+=1
        try:
            status,mime,location,raw=read(path)
            report["official_gets"].append(examine(scope,path,status,mime,location,raw))
        except Exception as e:
            report["errors"].append({
                "council_scope":scope,
                "exception_type":type(e).__name__,
                "message":str(e)[:180],
            })
    if len(report["official_gets"])==2 and not report["errors"] and all(
        p["parse_ok"] for p in report["official_gets"]
    ):
        report["result"]="PASS_BOTH_OFFICIAL_PREINTEGRATION_PORTAL_HTML_ACCESSIBLE"
    else:
        report["result"]="INCONCLUSIVE_OFFICIAL_PREINTEGRATION_PORTAL_ACCESS"
    out=Path(out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    r=probe()
    print(json.dumps(r,ensure_ascii=False,indent=2))
