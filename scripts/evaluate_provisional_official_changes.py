"""Fail-closed OFFLINE evaluator for scoped official provisional-status observations.

No HTTP and no live source mutation. A newly published record is only a
candidate, never proof that the current Markdown can be replaced without
fetching and versioning the true official body in a separate approved sync.

Only the explicitly observed 6 IDs are covered. This script does not claim
there were no other new meetings or changes across the complete archive.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/"indexes/integrated/initial_term_4.json"
LIVE=ROOT/"reports/official-six-provisional-status-20261102.json"
OUT=ROOT/"reports/official-six-provisional-change-candidates-20261102.json"
EXPECTED=("4017","4018","4019","4020","4021","4022")


def evaluate(saved:list[dict],live:dict)->dict:
    by_id={str(x["source_id"]):x for x in saved}
    if len(by_id)!=len(saved):
        raise ValueError("Duplicate archived source ID")
    if set(live.get("target_source_ids",[]))!=set(EXPECTED):
        raise ValueError("Official narrow-scope six-ID target changed")
    seen=live.get("results_by_id",{})
    result={
        "schema":"official-provisional-change-candidates/1",
        "source_live_report":"reports/official-six-provisional-status-20261102.json",
        "source_live_status":live.get("status"),
        "evaluation_scope":"ONLY six previously saved provisional meeting IDs",
        "review_candidates":[],
        "verified_unchanged":[],
        "unverified":[],
        "source_archive_modified":False,
        "full_official_inventory_verified":False,
        "production_update_authorized":False,
    }
    for sid in EXPECTED:
        old=by_id.get(sid)
        record=seen.get(sid)
        if not old or old.get("publication_status")!="provisional":
            raise ValueError("Unexpected original provisional baseline: "+sid)
        if not record or record.get("verification")!="CONFIRMED_LIVE_OFFICIAL_LEAF":
            result["unverified"].append({
                "source_id":sid,
                "reason":record.get("verification") if record else "MISSING_LIVE_RECORD",
                "action":"MANUAL_SOURCE_REVIEW_NO_AUTO_DELETION",
            })
            continue
        current=record.get("live_status")
        prior=old["publication_status"]
        if current not in {"published","provisional"}:
            result["unverified"].append({
                "source_id":sid,"reason":"UNKNOWN_LIVE_STATUS",
                "action":"MANUAL_SOURCE_REVIEW_NO_AUTO_DELETION"
            })
        elif prior!=current:
            result["review_candidates"].append({
                "source_id":sid,
                "stored_status":prior,
                "official_live_status":current,
                "stored_original_sha256":old["sha256"],
                "stored_original_path":old["path"],
                "next_action":"FETCH_LIVE_BODY_THEN_VERSION_IN_ISOLATED_SNAPSHOT",
                "auto_apply":False,
            })
        else:
            result["verified_unchanged"].append({
                "source_id":sid,
                "status":current,
                "stored_original_sha256":old["sha256"],
            })
    if len(result["review_candidates"])+len(result["verified_unchanged"])+len(result["unverified"])!=len(EXPECTED):
        raise RuntimeError("Missing or duplicate classification")
    if result["unverified"]:
        result["decision"]="INCOMPLETE_SIX_ID_OFFICIAL_OBSERVATION"
    elif result["review_candidates"]:
        result["decision"]="LIVE_STATUS_CHANGE_CANDIDATES_REQUIRING_BODY_VERIFICATION"
    else:
        result["decision"]="NO_CONFIRMED_STATUS_CHANGE_IN_SIX_PROVISIONAL_SOURCES"
    return result


def main():
    prior=json.loads(OLD.read_text(encoding="utf-8"))
    live=json.loads(LIVE.read_text(encoding="utf-8"))
    report=evaluate(prior,live)
    report["evaluated_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
    report["warning"]="This is not a full live inventory. No original file has been updated."
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
