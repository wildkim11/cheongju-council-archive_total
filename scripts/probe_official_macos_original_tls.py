"""Single-request macOS live official minutes test using ORIGINAL collector TLS.

Use the original collector's ssl.create_default_context + TLS1.2 minimum
+ TLS.set_ciphers("DEFAULT") to isolate its settings from the default-only
read-only probe. Secure certificate verification remains enabled.
No retries, no source archive writes, no run_sync, no full-tree crawl.
"""
import datetime as dt
import hashlib
import http.client
import json
import platform
import ssl
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import collect_integrated_minutes as c

OUT=ROOT/"reports/official-macos-original-tls-3999-20261102.json"
URL="https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=3999"
HOST="councilrec.cheongju.go.kr"
TARGET="/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=3999"


def probe(request_func=None,output=OUT):
    if platform.system()!="Darwin":
        raise RuntimeError("ORIGINAL_TLS_PROBE_REQUIRES_MACOS")
    source=json.loads((ROOT/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
    if len(source)!=2339:
        raise RuntimeError("Unexpected archived source meeting count")
    row=next((r for r in source if str(r["source_id"])=="3999"),None)
    if not row or row["official_url"]!=URL:
        raise RuntimeError("Saved official source URL mismatch")
    result={
        "schema":"official-macos-original-tls-readonly/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "runner":"macOS","runtime_platform":platform.platform(),
        "endpoint":URL,
        "source_id":"3999",
        "tls_context":"collect_integrated_minutes.TLS, original production collector configuration",
        "tls_version_minimum":"TLSv1.2",
        "cipher_suite_configuration":"DEFAULT (as in existing collector)",
        "certificate_validation_enabled":True,
        "http_request_limit":1,"http_requests_attempted":1,
        "automatic_retries":0,"timeout_seconds":12,
        "saved_source_rows":len(source),
        "stored_status":row["publication_status"],
        "stored_body_sha256":row["content_sha256"],
        "original_archive_writes":0,
        "production_collection_enabled":False,
        "http_status":None,"result":"NOT_EXECUTED",
    }
    def original_single_request():
        conn=http.client.HTTPSConnection(HOST,timeout=12,context=c.TLS)
        try:
            conn.request("GET",TARGET,None,{
                "User-Agent":"CheongjuCouncilArchive/0.1",
                "Content-Type":"application/x-www-form-urlencoded",
            })
            response=conn.getresponse()
            raw=response.read(12*1024*1024+1)
            if len(raw)>12*1024*1024:
                raise ValueError("LARGER_THAN_12_MIB")
            return response.status,raw
        finally:
            conn.close()
    try:
        status,raw=(request_func or original_single_request)()
        result["http_status"]=status
        result["raw_response_length"]=len(raw)
        result["raw_response_sha256"]=hashlib.sha256(raw).hexdigest()
        if status!=200:
            result["result"]="NON_200_HTTP_RESPONSE"
        else:
            body=c.extract_minutes_body(raw.decode("utf-8-sig"))
            body_hash=hashlib.sha256(c.canonical(body).encode("utf-8")).hexdigest()
            result["body_parsed"]=True
            result["live_body_sha256"]=body_hash
            result["matches_saved_body"]=body_hash==row["content_sha256"]
            result["result"]="PASS_SAVED_BODY_MATCH" if result["matches_saved_body"] else "BODY_CHANGED_MANUAL_REVIEW"
    except Exception as exc:
        result["result"]="INCONCLUSIVE_CONNECTION_OR_PARSER_FAILURE"
        result["error_type"]=type(exc).__name__
        result["error_message"]=str(exc)[:220]
    result["operational_release_authorized"]=False
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return result


if __name__=="__main__":
    print(json.dumps(probe(),indent=2,ensure_ascii=False))
