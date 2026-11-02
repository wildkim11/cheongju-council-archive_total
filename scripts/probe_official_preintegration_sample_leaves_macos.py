"""Bounded official legacy city/county drilldown to a real meeting leaf per scope.

Read the already VERIFIED government root nodes from previous macOS proof.
For each exact scope: 1 POST term->sessions, 1 POST last session->committees,
1 POST selected committee->leaves, 1 GET official portal HTML to discover
the actual viewer link syntax. No meeting bodies or archive writes yet.

Pick the latest numeric official session and its plenary committee if present.
No redirection to other hosts, max 8 GET/POST requests combined, no retry.
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
import urllib.parse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_integrated_minutes as collector

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"reports/official-preintegration-root-trees-readonly-20261102.json"
OUT=ROOT/"reports/official-preintegration-two-leaves-readonly-20261102.json"
HOST="councilrec.cheongju.go.kr"
SCOPE={
  "cheongju_old_city":{"prefix":"/minuteschj","root_term":"9",
      "portal":"/content/cityMinutes/prevsession.html"},
  "cheongwon_old_county":{"prefix":"/minuteschw","root_term":"6",
      "portal":"/content/gunMinutes/prevsession.html"},
}
MAX_REQUESTS=8
MAX_RESPONSE=2*1024*1024

def request(method,path,payload=None):
    if not any(path in (
       v["prefix"]+"/svc/web/cms/mnts/SvcMntsTreeGnrtn.php",
       v["portal"]) for v in SCOPE.values()):
        raise ValueError("Unverified official legacy URL")
    if method=="POST" and not payload:
        raise ValueError("Missing server-derived tree node variables")
    if payload is not None and any(not k.startswith("var") for k in payload):
        raise ValueError("Unsafe tree post payload")
    form=urllib.parse.urlencode(payload).encode("utf-8") if payload else None
    c=http.client.HTTPSConnection(HOST,timeout=12,context=collector.TLS)
    try:
        c.request(method,path,body=form,headers={
            "User-Agent":"CheongjuCouncilArchive/0.1",
            "Content-Type":"application/x-www-form-urlencoded",
        })
        r=c.getresponse()
        raw=r.read(MAX_RESPONSE+1)
        if len(raw)>MAX_RESPONSE:raise ValueError("Official bounded response too large")
        if r.status!=200:raise ValueError("Official HTTP "+str(r.status))
        return raw
    finally:
        c.close()

def values(node):
    return {k:v for k,v in node.items() if k.startswith("var")}

def find_viewer_references(source):
    fragments=[]
    for keyword in ("SvcMntsViewer","Viewer.php","schSn","goMnts","viewMnts","viewMinutes"):
        for match in list(re.finditer(re.escape(keyword),source,re.I))[:6]:
            snippet=" ".join(source[max(0,match.start()-100):min(len(source),match.end()+140)].split())
            fragments.append({"keyword":keyword,"source_context":snippet[:240]})
    urls=sorted(set(re.findall(
        r"/minutes(?:chj|chw)/[A-Za-z0-9_./?&=%-]*(?:php|html)(?:\?[A-Za-z0-9_=&%.-]+)?",
        source,re.I
    )))
    return {"viewer_contexts":fragments[:25],"literal_page_paths":urls[:25]}

def run(read=request,pause=time.sleep,out=OUT):
    if platform.system()!="Darwin":raise RuntimeError("macOS official probe only")
    previous=json.loads(SOURCE.read_text(encoding="utf-8"))
    if previous["status"]!="PASS_BOTH_PREINTEGRATION_TERM_ROOTS":
        raise RuntimeError("Official root proof is missing")
    verified={row["scope"]:row for row in previous["root_results"]}
    if set(verified)!=set(SCOPE):
        raise ValueError("Source council scope mismatch")
    report={
      "schema":"legacy-two-official-sampled-meeting-leaves/1",
      "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "request_cap":MAX_REQUESTS,"requests_attempted":0,
      "retries":0,"council_results":[],"errors":[],
      "archive_source_files_modified":False,
      "all_terms_enumerated":False,
      "meeting_bodies_fetched":0,
      "production_import_enabled":False,
    }
    def one(method,path,payload=None):
        if report["requests_attempted"]>=MAX_REQUESTS:
            raise ValueError("Official endpoint call limit exceeded")
        if report["requests_attempted"]:pause(0.35)
        report["requests_attempted"]+=1
        return read(method,path,payload)
    for scope,meta in SCOPE.items():
        result={"scope":scope,"selected_term":int(meta["root_term"])}
        try:
            saved_roots=verified[scope]["root_nodes"]
            roots=[r for r in saved_roots if str(r.get("var01"))==meta["root_term"]]
            if len(roots)!=1:raise ValueError("Missing verified official term")
            root=roots[0]
            endpoint=meta["prefix"]+"/svc/web/cms/mnts/SvcMntsTreeGnrtn.php"
            sessions=json.loads(one("POST",endpoint,values(root)).decode("utf-8-sig"))
            if not isinstance(sessions,list) or not sessions:raise ValueError("No official session array")
            allowed=[s for s in sessions
                     if str(s.get("var03") or "").isdigit() and str(s.get("var01"))==meta["root_term"]]
            if len(allowed)!=len(sessions):raise ValueError("Bad source session hierarchy")
            selected=max(allowed,key=lambda s:int(s["var03"]))
            result["official_sessions_in_selected_term"]=len(sessions)
            result["selected_session"]=str(selected["var03"])
            committees=json.loads(one("POST",endpoint,values(selected)).decode("utf-8-sig"))
            if not isinstance(committees,list) or not committees:raise ValueError("No committees under selected session")
            selected_comm=next((x for x in committees if
                x.get("var02")=="A010" or "본회의" in str(x.get("text",""))),committees[0])
            if str(selected_comm.get("var03"))!=result["selected_session"]:
                raise ValueError("Unexpected official committee session")
            result["official_committees_under_selected_session"]=len(committees)
            result["selected_committee"]=str(selected_comm.get("text",""))[:180]
            result["selected_committee_code"]=selected_comm.get("var02")
            leaves=json.loads(one("POST",endpoint,values(selected_comm)).decode("utf-8-sig"))
            if not isinstance(leaves,list):
                raise ValueError("Official leaves are not JSON array")
            result["leaf_count_in_selected_committee"]=len(leaves)
            result["leaf_source_samples"]=[
                {k:leaf.get(k) for k in ("text","var12","var09","var01","var02","var03")
                 if leaf.get(k) is not None}
                for leaf in leaves[:8] if isinstance(leaf,dict)
            ]
            html=one("GET",meta["portal"]).decode("utf-8-sig")
            result["viewer_reference_evidence"]=find_viewer_references(html)
            result["status"]="PASS_ONE_SCOPE_LEAF_BRANCH_VERIFIED"
            if not any(str(leaf.get("var12") or "").isdigit() for leaf in leaves):
                result["status"]="NO_VERIFIABLE_SOURCE_ID_IN_SELECTED_COMMITTEE"
        except Exception as e:
            result["status"]="INCONCLUSIVE_LEGACY_SCOPE_SAMPLE"
            report["errors"].append({
                "scope":scope,"type":type(e).__name__,"reason":str(e)[:190],
            })
        report["council_results"].append(result)
    report["status"]="PASS_BOTH_INDEPENDENT_LEGACY_SCOPE_LEAF_BRANCHES" if (
        not report["errors"] and all(row["status"]=="PASS_ONE_SCOPE_LEAF_BRANCH_VERIFIED"
                                    for row in report["council_results"])) else "INCONCLUSIVE_LEGACY_LEAF_BRANCHES"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    print(json.dumps(run(),ensure_ascii=False,indent=2))
