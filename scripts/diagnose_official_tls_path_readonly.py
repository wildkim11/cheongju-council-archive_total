"""At most two TLS-only handshakes to locate official-domain connectivity block.

No HTTP, no crawling, no POST, no archived-data writing. SECURE default TLS,
never disable certificate verification. One attempt per approved hostname.
A successful TLS handshake is not proof of HTTP or official viewer parsability.
"""
from __future__ import annotations

import datetime as dt
import json
import socket
import ssl
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HOSTS=("councilrec.cheongju.go.kr","council.cheongju.go.kr")
TIMEOUT_SECONDS=8
OUT=ROOT/"reports/official-readonly-tls-diagnostic-20261102.json"


def tls_check(host:str)->dict:
    if host not in HOSTS:
        raise ValueError("Domain not in official read-only allowlist")
    report={"host":host,"tcp_port":443,"attempts":1,"http_requests":0}
    try:
        with socket.create_connection((host,443),timeout=TIMEOUT_SECONDS) as raw:
            report["tcp_connection"]="connected"
            ctx=ssl.create_default_context()
            ctx.minimum_version=ssl.TLSVersion.TLSv1_2
            with ctx.wrap_socket(raw,server_hostname=host) as secured:
                secured.settimeout(TIMEOUT_SECONDS)
                report["tls"]="verified"
                report["negotiated_tls_version"]=secured.version()
                report["cipher"]=secured.cipher()[0] if secured.cipher() else None
    except Exception as exc:
        report["tls"]="not_verified"
        report["error_type"]=type(exc).__name__
        report["error"]=str(exc)[:180]
    return report


def diagnose(check=tls_check,out=OUT):
    data={
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "kind":"STRICT_TLS_ONLY_DIAGNOSTIC_NO_HTTP",
        "official_hosts":list(HOSTS),
        "max_tls_handshakes":2,
        "tls_handshakes_attempted":0,
        "http_requests":0,
        "certificate_verification_disabled":False,
        "saved_archive_modified":False,
        "production_sync_enabled":False,
        "hosts":[],
    }
    for host in HOSTS:
        x=check(host)
        data["hosts"].append(x)
        data["tls_handshakes_attempted"]+=1
    first,second=data["hosts"]
    if first.get("tls")=="verified":
        data["status"]="OFFICIAL_MINUTES_HOST_TLS_AVAILABLE_FROM_THIS_RUNNER"
    elif second.get("tls")=="verified":
        data["status"]="MINUTES_HOST_TLS_UNAVAILABLE_BUT_COUNCIL_MAIN_HOST_AVAILABLE"
    else:
        data["status"]="OFFICIAL_TLS_UNAVAILABLE_FROM_THIS_RUNNER"
    data["no_inference_about_server_global_uptime"]=True
    data["live_collection_authorized"]=False
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return data


if __name__=="__main__":
    print(json.dumps(diagnose(),ensure_ascii=False,indent=2))
