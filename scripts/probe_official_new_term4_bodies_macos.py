"""At most two HTTPS viewer GETs for confirmed new term-4 IDs, macOS only.

Retrieve and parse bodies for newly-discovered IDs 4024 and 4025, using the
identical secure TLS context as the original 2339-source collector. The script
writes only small metadata/hash proof, never HTML, text or any archive file.
Do not automatically accept new IDs into canonical archive without a distinct
isolated incremental rehearsal and explicit production approval.
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import collect_integrated_minutes as original

HOST="councilrec.cheongju.go.kr"
BASE="/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="
DISCOVERY=ROOT/"reports/official-term4-new-meeting-id-discovery-20261102.json"
INDEX=ROOT/"indexes/integrated/meetings.json"
OUT=ROOT/"reports/official-term4-new-meeting-body-check-20261102.json"
EXPECTED_NEW_IDS=("4024","4025")
MAX_BYTES=8*1024*1024
MAX_CALLS=2


def get_viewer(sid:str)->tuple[int,bytes]:
    if sid not in EXPECTED_NEW_IDS:
        raise ValueError("Not authorized to GET arbitrary official meeting ID")
    conn=http.client.HTTPSConnection(HOST,timeout=12,context=original.TLS)
    try:
        conn.request("GET",BASE+sid,None,{
            "User-Agent":"CheongjuCouncilArchive/0.1",
            "Content-Type":"application/x-www-form-urlencoded",
        })
        response=conn.getresponse()
        raw=response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            raise ValueError("Official HTML exceeded 8MiB read-only limit")
        return response.status,raw
    finally:
        conn.close()


def classify_body(source:dict,http_status:int,raw:bytes)->dict:
    sid=str(source["source_id"])
    result={
        "source_id":sid,
        "official_url":source["official_url"],
        "official_meeting_date":source["official_date"],
        "official_tree_publication_status":source["official_status"],
        "http_status":http_status,
        "response_bytes":len(raw),
        "response_sha256":hashlib.sha256(raw).hexdigest(),
    }
    if http_status!=200:
        result["verification"]="NON_200_HTTP_INCONCLUSIVE"
        return result
    try:
        raw_text=raw.decode("utf-8-sig")
        body=original.extract_minutes_body(raw_text)
        body_hash=hashlib.sha256(original.canonical(body).encode("utf-8")).hexdigest()
        result["body_extracted"]=True
        result["body_normalized_sha256"]=body_hash
        result["body_characters"]=len(body)
        result["provisional_notice_present"]="임시회의록" in body
        result["verification"]=(
            "BODY_EXTRACTED_OFFICIAL_NEW_ID"
            if source["official_status"]=="published" or result["provisional_notice_present"]
            else "BODY_EXTRACTED_BUT_PROVISIONAL_NOTICE_NOT_FOUND_REVIEW"
        )
    except Exception as exc:
        result["body_extracted"]=False
        result["verification"]="BODY_PARSER_FAILURE_REVIEW"
        result["parse_error_type"]=type(exc).__name__
        result["parse_error"]=str(exc)[:180]
    return result


def run(read=get_viewer,out=OUT,sleep=time.sleep)->dict:
    if platform.system()!="Darwin":
        raise RuntimeError("Official read-only test requires macOS")
    verified=json.loads(DISCOVERY.read_text(encoding="utf-8"))
    if not verified.get("official_term4_coverage_complete") or verified.get("branch_errors"):
        raise ValueError("Official inventory discovery incomplete")
    candidates=verified["new_source_id_candidates"]
    ids=tuple(sorted(str(x["source_id"]) for x in candidates))
    if ids!=EXPECTED_NEW_IDS:
        raise ValueError("Bounded new source candidate list changed")
    old=json.loads(INDEX.read_text(encoding="utf-8"))
    old_ids={str(x["source_id"]) for x in old}
    if len(old)!=2339 or any(sid in old_ids for sid in ids):
        raise ValueError("Canonical pre-update 2339-source baseline mismatch")
    entries={str(x["source_id"]):x for x in candidates}
    if any(x["official_status"]!="provisional" for x in candidates):
        raise ValueError("Expected both newly discovered sources to be provisional")
    result={
        "schema":"official-new-term4-body-readonly-check/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "runner":"GitHub macOS original verified collector TLS",
        "source_discovery":"reports/official-term4-new-meeting-id-discovery-20261102.json",
        "max_requests":MAX_CALLS,
        "requests_attempted":0,
        "retries":0,
        "expected_new_ids":list(EXPECTED_NEW_IDS),
        "responses":[],
        "errors":[],
        "existing_saved_meetings":len(old),
        "canonical_new_sources_published":0,
        "source_archive_modified":False,
        "production_collection_enabled":False,
        "operational_release_authorized":False,
    }
    for sid in ids:
        if result["requests_attempted"]:
            sleep(0.35)
        result["requests_attempted"]+=1
        try:
            status,body=read(sid)
            entry=classify_body(entries[sid],status,body)
            result["responses"].append(entry)
            if entry["verification"]!="BODY_EXTRACTED_OFFICIAL_NEW_ID":
                result["errors"].append({
                    "source_id":sid,
                    "reason":entry["verification"],
                })
                break
        except Exception as exc:
            result["errors"].append({
                "source_id":sid,
                "exception_type":type(exc).__name__,
                "message":str(exc)[:180],
            })
            break
    result["body_parsed_count"]=sum(x.get("body_extracted") is True for x in result["responses"])
    result["decision"]=(
        "BOTH_NEW_OFFICIAL_BODIES_READABLE_READY_FOR_ISOLATED_IMPORT_REHEARSAL"
        if not result["errors"] and len(result["responses"])==2
        else "INCOMPLETE_NEW_OFFICIAL_BODY_VERIFICATION"
    )
    result["warning"]="Body hashes prove the two pages were readable; no canonical source file has been added, and no automated promotion is authorized."
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result

if __name__=="__main__":
    print(json.dumps(run(),ensure_ascii=False,indent=2))
