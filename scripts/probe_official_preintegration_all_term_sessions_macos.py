"""Exact historical session inventory per all 12 official pre-2014 council terms.

One official POST per root (6 old Cheongju city, 6 old Cheongwon county),
using source-issued var01..var12 from the verified 2-root live report.
No committee/meeting body fetch, no source mutations, no retries.
This quantifies scope for planned term-by-term offline first backfill.
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
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_integrated_minutes as collector

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"reports/official-preintegration-root-trees-readonly-20261102.json"
OUT=ROOT/"reports/official-preintegration-12-terms-sessions-readonly-20261102.json"
HOST="councilrec.cheongju.go.kr"
COUNCILS={
"cheongju_old_city":{"prefix":"/minuteschj","terms":set(range(4,10))},
"cheongwon_old_county":{"prefix":"/minuteschw","terms":set(range(1,7))},
}
MAX_REQUESTS=12

def post(path,node):
    valid={s["prefix"]+"/svc/web/cms/mnts/SvcMntsTreeGnrtn.php" for s in COUNCILS.values()}
    if path not in valid:
        raise ValueError("Official unrecognized historical session endpoint")
    data={k:v for k,v in node.items() if k.startswith("var")}
    if not data or "var01" not in data:
        raise ValueError("Source verified generation root missing")
    c=http.client.HTTPSConnection(HOST,timeout=12,context=collector.TLS)
    try:
        c.request("POST",path,urllib.parse.urlencode(data).encode("utf-8"),
                  headers={"User-Agent":"CheongjuCouncilArchive/0.1",
                           "Content-Type":"application/x-www-form-urlencoded"})
        r=c.getresponse()
        raw=r.read(2*1024*1024+1)
        if r.status!=200 or len(raw)>2*1024*1024:
            raise ValueError("Official historical term sessions HTTP/size failure")
        nodes=json.loads(raw.decode("utf-8-sig"))
        if not isinstance(nodes,list):
            raise ValueError("Invalid official sessions JSON")
        return nodes
    finally:c.close()

def run(read=post,pause=time.sleep,out=OUT):
    if platform.system()!="Darwin":raise RuntimeError("Official macOS source only")
    rootproof=json.loads(SOURCE.read_text(encoding="utf-8"))
    if rootproof.get("status")!="PASS_BOTH_PREINTEGRATION_TERM_ROOTS":
        raise ValueError("Missing verified official historical roots")
    roots={r["scope"]:r["root_nodes"] for r in rootproof["root_results"]}
    if set(roots)!=set(COUNCILS):raise ValueError("Verified scopes wrong")
    result={
     "schema":"official-legacy-12-historical-term-session-counts/1",
     "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
     "request_cap":MAX_REQUESTS,"requests_attempted":0,"retries":0,
     "official_term_session_counts":[],"errors":[],
     "all_12_term_session_branches_verified":False,
     "all_official_meeting_leaf_counts_verified":False,
     "full_legacy_meeting_body_backfill_completed":False,
     "legacy_archives_modified":False,
     "integrated_archive_modified":False,
     "production_sync_enabled":False,
    }
    for scope,meta in COUNCILS.items():
        nodes=roots.get(scope,[])
        terms=[int(str(r.get("var01") or "0")) for r in nodes]
        if set(terms)!=meta["terms"] or len(terms)!=6:
            raise ValueError("Official legacy scope terms changed")
        for root in sorted(nodes,key=lambda r:int(r["var01"])):
            if result["requests_attempted"]:
                pause(0.35)
            result["requests_attempted"]+=1
            term=int(root["var01"])
            try:
                rows=read(meta["prefix"]+"/svc/web/cms/mnts/SvcMntsTreeGnrtn.php",root)
                ses=[str(x.get("var03") or "") for x in rows]
                if not rows or any(not x.isdigit() or str(row.get("var01"))!=str(term)
                                   for x,row in zip(ses,rows)):
                    raise ValueError("Unexpected missing/invalid official session code")
                if len(set(ses))!=len(ses):
                    raise ValueError("Duplicate official session code")
                result["official_term_session_counts"].append({
                    "scope":scope,"term":term,
                    "official_term_label":str(root.get("text",""))[:180],
                    "verified_session_count":len(rows),
                    "min_session_number":min(map(int,ses)),
                    "max_session_number":max(map(int,ses)),
                    "complete_session_node_list_verified":True,
                    "meeting_record_count_not_yet_verified":True,
                })
            except Exception as e:
                result["errors"].append({
                   "scope":scope,"term":term,"type":type(e).__name__,
                   "reason":str(e)[:180],
                })
    result["all_12_term_session_branches_verified"]=(len(result["official_term_session_counts"])==12 and not result["errors"])
    result["total_verified_historical_session_nodes"]=sum(x["verified_session_count"] for x in result["official_term_session_counts"])
    result["status"]="PASS_ALL_12_OFFICIAL_LEGACY_TERM_SESSION_COUNTS" if result["all_12_term_session_branches_verified"] else "INCONCLUSIVE_12_HISTORICAL_TERM_COUNTS"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result
if __name__=="__main__":print(json.dumps(run(),ensure_ascii=False,indent=2))
