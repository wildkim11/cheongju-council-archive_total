"""Verify lossless source-only partition for individual member proposer analytics.

Writes a QA report but does not alter canonical bill facts or relationships.
"""
from __future__ import annotations
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
from export_analyzer import partition_bill_proposer_rows
from archive_common import save_json

ROOT=Path(__file__).resolve().parents[1]
EXPECTED_INSTITUTIONAL={"375":1,"2177":6,"2180":12,"3265":12,"3266":13}

def verify(root=ROOT):
    canonical_bills=root/"archive/bills/items.json"
    canonical_links=root/"archive/bills/proposer_memberships.json"
    bills=json.loads(canonical_bills.read_text(encoding="utf-8"))
    original=json.loads(canonical_links.read_text(encoding="utf-8"))
    personal,quarantine=partition_bill_proposer_rows(bills,original)
    manifest=json.loads((root/"exports/analyzer/manifest.json").read_text(encoding="utf-8"))
    names=("bill_proposers","bill_proposers_member_only","bill_proposers_institutional_type_quarantine")
    actual={}
    for key in names:
        entry=manifest["datasets"][key]
        path=root/entry["path"]
        payload=path.read_bytes()
        actual[key]=[json.loads(line) for line in payload.splitlines() if line.strip()]
        if hashlib.sha256(payload).hexdigest()!=entry["sha256"] or len(actual[key])!=entry["rows"]:
            raise ValueError(f"analyzer manifest and JSONL do not agree: {key}")
    if actual["bill_proposers"]!=original or actual["bill_proposers_member_only"]!=personal or actual["bill_proposers_institutional_type_quarantine"]!=quarantine:
        raise ValueError("Source-proposer export partition not exactly lossless")
    counts=dict(collections.Counter(str(x["internal_number"]) for x in quarantine))
    if counts!=EXPECTED_INSTITUTIONAL:
        raise ValueError(f"Institutional quarantine set unexpectedly changed: {counts}")
    if len(personal)!=11377 or len(quarantine)!=44 or len(original)!=11421:
        raise ValueError("Unexpected baseline counts for current 2026-11-02 source snapshot")
    principles=manifest["principles"]
    if principles.get("personal_proposer_statistics_dataset")!="bill_proposers_member_only":
        raise ValueError("Recommended member-only dataset not declared")
    if principles.get("institutional_type_person_names_quarantined_dataset")!="bill_proposers_institutional_type_quarantine":
        raise ValueError("Missing institutional quarantine manifest declaration")
    result={
        "checked_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "status":"PASS",
        "source_bills":len(bills),
        "raw_legacy_person_relationships":len(original),
        "verified_personal_proposer_relationships":len(personal),
        "institutional_type_relationships_separated":len(quarantine),
        "affected_institutional_bill_ids":counts,
        "canonical_bill_sha256":hashlib.sha256(canonical_bills.read_bytes()).hexdigest(),
        "canonical_proposer_link_sha256":hashlib.sha256(canonical_links.read_bytes()).hexdigest(),
        "member_only_export":manifest["datasets"]["bill_proposers_member_only"],
        "quarantine_export":manifest["datasets"]["bill_proposers_institutional_type_quarantine"],
        "source_archive_mutated_by_this_audit":False,
        "note":"Institutional proposer_type appears for all 44 records; specific personal roles in underlying document have not been authoritatively determined.",
    }
    save_json(root/"reports/bill-proposer-safe-export.json",result)
    return result

if __name__=="__main__":
    r=verify()
    print(json.dumps({k:v for k,v in r.items() if not k.endswith("sha256")},ensure_ascii=False,indent=2))
