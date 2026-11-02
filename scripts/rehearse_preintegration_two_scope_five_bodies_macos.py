"""Five-real-body, two-council, TEMPORARY initial backfill rehearsal.

The official term/session/committee/leaf paths and viewer URL syntax were
previously proven from the original sources, not inferred. This rehearsal
GETs the complete sample leaf set from two independent historical councils
(3 old Cheongju city + 2 old Cheongwon county), writes only to a disposable
temporary staging tree, and removes it after SHA and identity verification.

The source status code N is kept RAW and UNINTERPRETED until independently
supported by historic official evidence. No current analyzer promotion or
existing 2339-source update, and no data loss on source failure.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import http.client
import json
import platform
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import collect_integrated_minutes as collector
import legacy_minutes_scope_contract as policy

PROOF=ROOT/"reports/official-preintegration-two-leaves-readonly-20261102.json"
PRIOR=ROOT/"reports/official-preintegration-two-real-bodies-readonly-20261102.json"
FULL_TERMS=ROOT/"reports/official-preintegration-12-terms-sessions-readonly-20261102.json"
OUT=ROOT/"reports/official-preintegration-five-bodies-isolated-pilot-20261102.json"
HOST="councilrec.cheongju.go.kr"
MAX_GET=5
MAX_HTML=8*1024*1024
HISTORIC_PROOF_SHA={
    ("cheongju_old_city","4355"):"aa8009f8fbdd5b6a2eccf86bd6b863951590503764de66724b8b4c825ba905cd",
    ("cheongwon_old_county","2581"):"238b6064a2b51113cdd11afbbc179004354a4cc50d97fa51f599534a9db83e57",
}

def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def get_one(url):
    prefix="https://"+HOST
    if not url.startswith(prefix) or "?" not in url:
        raise ValueError("Official URL not verified")
    relative=url[len(prefix):]
    c=http.client.HTTPSConnection(HOST,timeout=12,context=collector.TLS)
    try:
        c.request("GET",relative,headers={"User-Agent":"CheongjuCouncilArchive/0.1"})
        r=c.getresponse()
        raw=r.read(MAX_HTML+1)
        if len(raw)>MAX_HTML:
            raise ValueError("Too much HTML from official sample")
        return r.status,raw
    finally:c.close()

def run(read=get_one,pause=time.sleep,out=OUT):
    if platform.system()!="Darwin":raise RuntimeError("Only isolated macOS official source validation")
    prior=json.loads(PRIOR.read_text(encoding="utf-8"))
    leaves=json.loads(PROOF.read_text(encoding="utf-8"))
    terms=json.loads(FULL_TERMS.read_text(encoding="utf-8"))
    if prior["status"]!="PASS_TWO_OFFICIAL_LEGACY_BODIES" or leaves["status"]!="PASS_BOTH_INDEPENDENT_LEGACY_SCOPE_LEAF_BRANCHES":
        raise ValueError("Missing verified legacy original source proof")
    if terms["status"]!="PASS_ALL_12_OFFICIAL_LEGACY_TERM_SESSION_COUNTS":
        raise ValueError("Official historical 437-session sizing not verified")
    check={(r["scope"],r["meeting_source_id"]):r["normalized_body_sha256"] for r in prior["responses"]}
    if check!=HISTORIC_PROOF_SHA:
        raise ValueError("Previously observed historical body hashes have changed")
    report={
        "schema":"official-two-legacy-councils-five-body-disposable-staging/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "original_term_session_nodes_in_all_12_terms":terms["total_verified_historical_session_nodes"],
        "initial_source_coverage":"5 verified leaf ID samples only; NOT full historic inventories",
        "requests_attempted":0,"request_limit":MAX_GET,"retries":0,
        "body_rows":[],"errors":[],
        "staged_original_markdown_count":0,
        "staging_removed_after_run":False,
        "source_archive_modified":False,
        "integrated_original_files_modified":False,
        "production_backfill_enabled":False,
        "analyzer_publication_enabled":False,
        "historic_N_code_normalized":False,
    }
    with tempfile.TemporaryDirectory(prefix="cheongju-historical-two-scope-five-real-") as tmp:
        stage=Path(tmp)/"staging"
        stage.mkdir()
        records=[]
        for sample in leaves["council_results"]:
            scope=sample["scope"]
            if scope not in policy.SCOPE_TERM_RANGES:raise ValueError("Unexpected council scope")
            for leaf in sample["leaf_source_samples"]:
                if report["requests_attempted"]>=MAX_GET:
                    raise RuntimeError("Unexpected extra official legacy viewer request")
                row=policy.normalize_verified_legacy_leaf(
                    scope,sample["selected_term"],sample["selected_session"],
                    sample["selected_committee_code"],leaf)
                if report["requests_attempted"]:
                    pause(0.35)
                report["requests_attempted"]+=1
                status,raw=read(row["official_url"])
                if status!=200:raise ValueError("Official source HTTP "+str(status))
                body=collector.extract_minutes_body(raw.decode("utf-8-sig"))
                content_sha=hashlib.sha256(collector.canonical(body).encode("utf-8")).hexdigest()
                previous=HISTORIC_PROOF_SHA.get((scope,row["source_id"]))
                if previous and previous!=content_sha:
                    raise RuntimeError("HISTORIC_REAL_BODY_DRIFT_BEFORE_ISOLATED_IMPORT: "+str(row["meeting_id"]))
                # Only the TempDirectory receives a source transcript. Never
                # publish it in the version-controlled repository.
                rel=Path("meetings")/scope/f"term-{row['term']}"/str(row["year"])/f"minutes-{row['source_id']}.md"
                path=stage/rel
                path.parent.mkdir(parents=True,exist_ok=True)
                marker="\n\n## 원문 (독립 검증용 임시 스냅샷)\n\n"
                contents=(
                    "# Official source staging: "+row["meeting_id"]+"\n\n"+
                    json.dumps(row,ensure_ascii=False,sort_keys=True)+"\n"+
                    marker+body+"\n"
                )
                path.write_text(contents,encoding="utf-8")
                reread=path.read_text(encoding="utf-8")
                if marker not in reread:
                    raise AssertionError("Missing original content marker")
                from_file=reread.split(marker,1)[1].rstrip("\n")
                if hashlib.sha256(collector.canonical(from_file).encode("utf-8")).hexdigest()!=content_sha:
                    raise RuntimeError("SOURCE_ROUND_TRIP_HASH_MISMATCH: "+row["meeting_id"])
                row["staging_relative_path"]=str(rel)
                row["staging_markdown_sha256"]=file_sha(path)
                row["normalized_body_sha256"]=content_sha
                row["normalized_body_characters"]=len(body)
                records.append(row)
                report["body_rows"].append({
                    "council_scope":scope,
                    "source_id":row["source_id"],
                    "meeting_id":row["meeting_id"],
                    "official_url":row["official_url"],
                    "http_status":status,
                    "content_sha256":content_sha,
                    "source_markdown_sha256":row["staging_markdown_sha256"],
                    "body_characters":len(body),
                    "stored_status_code":row["source_tree_publication_code"],
                    "normalized_status":row["normalized_publication_status"],
                    "eligible_for_public_analyzer":False,
                })
        if report["requests_attempted"]!=MAX_GET or len(records)!=MAX_GET:
            raise RuntimeError("Expected exactly 5 real body samples")
        contract=policy.check_stage_scope_collisions(records)
        if len({row["meeting_id"] for row in records})!=5:
            raise RuntimeError("Scope namespaced meeting ID duplicated")
        report["staged_original_markdown_count"]=len(records)
        report["scope_counts"]={scope:sum(row["council_scope"]==scope for row in records)
                                for scope in policy.SCOPE_TERM_RANGES}
        report["verified_scope_contract"]=contract
        for row in records:
            path=stage/row["staging_relative_path"]
            if file_sha(path)!=row["staging_markdown_sha256"]:
                raise RuntimeError("FILE_SHA_CHANGED_BEFORE_TEMP_CLEANUP")
    report["staging_removed_after_run"]=True
    report["status"]="PASS_FIVE_REAL_OFFICIAL_LEGACY_BODIES_IN_DISPOSABLE_SCOPE_ISOLATED_STAGING"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report
if __name__=="__main__":
    print(json.dumps(run(),ensure_ascii=False,indent=2))
