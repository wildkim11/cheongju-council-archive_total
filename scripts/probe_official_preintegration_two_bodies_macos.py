"""Real two pre-2014 official meeting body read-only checks on GitHub macOS.

URLs are EXACTLY the href syntax from each legacy council's official
jquery.treeview.async.svc.mnts.js and source IDs from the verified LAST
session leaf tree. Untrusted source text NEVER gets executed.
GET 1 meeting per separate council, no retries, max 8MiB each.
Record cryptographic hashes, extraction count, status markers, never source
body text or archive originals.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import http.client
import json
import platform
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_integrated_minutes as integrated

ROOT=Path(__file__).resolve().parents[1]
LEAVES=ROOT/"reports/official-preintegration-two-leaves-readonly-20261102.json"
REFERENCES=ROOT/"reports/official-preintegration-viewer-js-readonly-20261102.json"
OUT=ROOT/"reports/official-preintegration-two-real-bodies-readonly-20261102.json"
HOST="councilrec.cheongju.go.kr"
SELECTED={
    "cheongju_old_city":{"source_id":"4355","prefix":"/minuteschj"},
    "cheongwon_old_county":{"source_id":"2581","prefix":"/minuteschw"},
}
MAX_RESPONSE=8*1024*1024

def get(relative):
    valid={
        s["prefix"]+f"/svc/web/cms/mnts/SvcMntsViewer.php?schSn={s['source_id']}"
        for s in SELECTED.values()
    }
    if relative not in valid:
        raise ValueError("Viewer request is not from JS+leaf verified exact sample")
    c=http.client.HTTPSConnection(HOST,timeout=12,context=integrated.TLS)
    try:
        c.request("GET",relative,headers={"User-Agent":"CheongjuCouncilArchive/0.1"})
        response=c.getresponse()
        raw=response.read(MAX_RESPONSE+1)
        if len(raw)>MAX_RESPONSE:raise ValueError("Official sample HTML too large")
        return response.status,response.getheader("Content-Type"),raw
    finally:
        c.close()

def interpret(scope,sid,path,status,content_type,raw):
    result={
       "scope":scope,
       "meeting_source_id":sid,
       "official_url":"https://"+HOST+path,
       "http_status":status,
       "content_type":content_type,
       "raw_response_bytes":len(raw),
       "raw_html_sha256":hashlib.sha256(raw).hexdigest(),
       "body_extracted":False,
       "archive_body_written":False,
    }
    if status!=200:
        result["verification"]="OFFICIAL_SAMPLE_HTTP_NON_200"
        return result
    try:
        page=raw.decode("utf-8-sig")
        body=integrated.extract_minutes_body(page)
        digest=hashlib.sha256(integrated.canonical(body).encode("utf-8")).hexdigest()
        result.update({
            "body_extracted":True,
            "normalized_body_characters":len(body),
            "normalized_body_sha256":digest,
            "html_contains_provisional_notice":("임시회의록" in page),
            "body_contains_provisional_notice":("임시회의록" in body),
            "verification":"PASS_REAL_OFFICIAL_LEGACY_BODY",
        })
    except Exception as error:
        result["verification"]="OFFICIAL_LEGACY_VIEWER_BODY_PARSE_INCONCLUSIVE"
        result["parser_error_type"]=type(error).__name__
        result["parser_error"]=str(error)[:180]
        # Only structural markers; no source body text stored.
        text=raw.decode("utf-8-sig",errors="replace")
        result["html_markers"]={marker:text.count(marker) for marker in (
            "<!-- 회의록내용 -->","<!--// 회의록내용", "<div id='anh'>",
            "minutesContent","임시회의록","본문"
        )}
    return result

def run(read=get,pause=time.sleep,out=OUT):
    if platform.system()!="Darwin":raise RuntimeError("Official legacy sample QA macOS-only")
    leaf=json.loads(LEAVES.read_text(encoding="utf-8"))
    ref=json.loads(REFERENCES.read_text(encoding="utf-8"))
    if (leaf.get("status")!="PASS_BOTH_INDEPENDENT_LEGACY_SCOPE_LEAF_BRANCHES"
        or ref.get("status")!="PASS_TWO_OFFICIAL_VIEWER_CLICK_JS_READ"):
        raise ValueError("Live official leaf or viewer URL provenance missing")
    indexed={x["scope"]:x for x in leaf["council_results"]}
    js={x["scope"]:x for x in ref["sources"]}
    report={
        "schema":"official-two-legacy-real-meeting-bodies/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source":"legacy official leaf plus official JS hyperlink verified",
        "requests_attempted":0,"request_limit":2,"retries":0,
        "responses":[],"errors":[],
        "official_meeting_bodies_saved_to_archive":0,
        "existing_integrated_originals_modified":False,
        "production_collector_enabled":False,
    }
    for scope,metadata in SELECTED.items():
        sid=metadata["source_id"]
        path=metadata["prefix"]+"/svc/web/cms/mnts/SvcMntsViewer.php?schSn="+sid
        if not any(str(l.get("var12"))==sid for l in indexed[scope]["leaf_source_samples"]):
            raise ValueError("Meeting sample is not an official verified leaf: "+sid)
        if not js[scope].get("viewer_reference_confirmed") or not any(
            path.rsplit("?schSn=",1)[0] in x for x in js[scope].get("php_references",[])
        ):
            raise ValueError("Official JS did not independently confirm viewer URL")
        if report["requests_attempted"]:pause(0.35)
        report["requests_attempted"]+=1
        try:
            status,mime,raw=read(path)
            report["responses"].append(interpret(scope,sid,path,status,mime,raw))
        except Exception as error:
            report["errors"].append({
                "scope":scope,"source_id":sid,"type":type(error).__name__,
                "reason":str(error)[:180],
            })
    report["status"]="PASS_TWO_OFFICIAL_LEGACY_BODIES" if len(report["responses"])==2 and not report["errors"] and all(x["verification"]=="PASS_REAL_OFFICIAL_LEGACY_BODY" for x in report["responses"]) else "INCONCLUSIVE_LEGACY_OFFICIAL_BODIES"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report
if __name__=="__main__":print(json.dumps(run(),ensure_ascii=False,indent=2))
