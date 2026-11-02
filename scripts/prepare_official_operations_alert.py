"""Prepare stable deduplicated GitHub Issue alert metadata from monitor artifacts.

Never sends a network request. Real issue creation is restricted to the
default-branch scheduled workflow alert job, after explicit release gating.
The GitHub issue is an audit trail, not proof of email or push delivery.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TERM4=ROOT/"reports/official-incremental-monitor-readonly-latest.json"
HISTORY=ROOT/"reports/official-historical-rolling-readonly-latest.json"
OUT=ROOT/"reports/official-operations-alert-latest.json"
BODY=ROOT/"reports/official-operations-alert-body.md"


def load(path):
    path=Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def ids(records):
    return sorted({str(r.get("source_id")) for r in records or []
                   if str(r.get("source_id","")).isdigit()},key=int)


def classify(term4:dict|None,history:dict|None,job_result:str)->dict:
    failed=job_result!="success"
    if (not term4 or term4.get("status","").startswith("BLOCKED_")
        or not history or history.get("status","").startswith("BLOCKED_")):
        failed=True
    t4=term4 or {}
    hist=history or {}
    candidates={
        "new_source_ids":ids(t4.get("new_ids",[])+hist.get("new_id_candidates",[])),
        "status_change_ids":ids(t4.get("status_change_candidates",[])),
        "metadata_change_ids":ids(t4.get("metadata_change_candidates",[])
                                 +hist.get("metadata_or_status_candidates",[])),
        "body_change_ids":ids(t4.get("body_change_candidates",[])),
        "historical_cross_term_ids":ids(hist.get("cross_term_id_candidates",[])),
    }
    active=any(candidates.values())
    category=("error" if failed else "review" if active else "none")
    identity={"category":category,"candidate_ids":candidates}
    if category=="error":
        identity["failed_sources"]={
            "term4":t4.get("status","ABSENT"),
            "historic":hist.get("status","ABSENT"),
            "job":job_result,
        }
    fingerprint=hashlib.sha256(
        json.dumps(identity,sort_keys=True,ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:20]
    return {
        "schema":"official-monitor-issue-alert/1",
        "kind":category,
        "title":{
            "error":"[자동감시 장애] 청주시의회 공식 회의록",
            "review":"[자동감시 변경후보] 청주시의회 공식 회의록",
            "none":""
        }[category],
        "fingerprint":fingerprint,
        "candidates":candidates,
        "source_statuses":{"term4":t4.get("status","ABSENT"),
                           "historical":hist.get("status","ABSENT"),
                           "workflow_job":job_result},
        "no_archive_changes":True,
        "notification_delivery_confirmed":False,
    }


def prepare(output=OUT,body_path=BODY,term4_path=TERM4,history_path=HISTORY,
            job_result="success",run_url=None,github_output=None):
    alert=classify(load(term4_path),load(history_path),job_result)
    alert["evaluated_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
    alert["workflow_run_url"]=run_url
    output=Path(output)
    body_path=Path(body_path)
    output.parent.mkdir(parents=True,exist_ok=True)
    body_path.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(alert,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=[
        "## 청주시의회 공식 회의록 자동감시",
        "",
        f"- 구분: **{alert['kind']}**",
        f"- 감시 상태: 제4대={alert['source_statuses']['term4']}, "
        f"제1~3대={alert['source_statuses']['historical']}",
        f"- 재현 지문: **FINGERPRINT={alert['fingerprint']}**",
        "- 이번 작업은 읽기전용으로 원본·인덱스·분석기를 변경하지 않았습니다.",
        f"- 실행 기록: {run_url or '실행 주소 없음'}",
        "",
    ]
    for label,values in alert["candidates"].items():
        if values:
            lines.append(f"- {label}: {', '.join(values)}")
    lines += [
        "",
        "이 이슈는 오류/변경 후보의 추적 기록입니다. 실제 이메일·푸시 알림이",
        "수신됐다는 증거가 아니며, 운영 자동수집을 승인하지 않습니다.",
    ]
    body_path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    if github_output:
        with open(github_output,"a",encoding="utf-8") as f:
            f.write(f"kind={alert['kind']}\n")
            f.write(f"fingerprint={alert['fingerprint']}\n")
            f.write(f"title={alert['title']}\n")
    print(json.dumps({"kind":alert["kind"],"fingerprint":alert["fingerprint"],
        "candidate_counts":{k:len(v) for k,v in alert["candidates"].items()}},
        ensure_ascii=False))
    return alert


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--job-result",default="success")
    ap.add_argument("--run-url",default=os.environ.get("GITHUB_RUN_URL",""))
    ap.add_argument("--output",type=Path,default=OUT)
    ap.add_argument("--body",type=Path,default=BODY)
    args=ap.parse_args()
    prepare(output=args.output,body_path=args.body,
        job_result=args.job_result,run_url=args.run_url,
        github_output=os.environ.get("GITHUB_OUTPUT"))
