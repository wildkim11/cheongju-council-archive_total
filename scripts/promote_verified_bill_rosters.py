"""One-time guarded promotion of *fully evidenced* official minutes proposer rosters.

Only 17 missing member-bill rosters with explicit title-adjacent full proposer
lists and unique same-term identities are eligible. Raw source fields and the
meeting archive stay unchanged. The workflow performs validation *before*
publishing these derived canonical bill facts.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from archive_common import save_json
from audit_bill_archive import audit
from export_analyzer import export
from link_bill_proposers import link
from reconcile_bill_proposers_from_minutes import recover
from validate_archive import validate

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def promote_one(row, proof, meeting_by_id, stamp):
    if proof["status"] != "full_roster_evidenced_not_promoted":
        raise ValueError("proof is not complete")
    if (row.get("proposer_type_list") or row.get("proposer_type")) != "의원":
        raise ValueError(f"non-member bill must not get people: {row['internal_number']}")
    if row.get("full_proposer_names") or row.get("representative_proposers"):
        raise ValueError(f"bill is not missing a roster: {row['internal_number']}")
    extracted = proof["verified_full_roster"]
    if not extracted:
        raise ValueError("missing verified full roster")
    names = extracted["all_names"]
    rep = extracted["representative"]
    if len(names) != len(set(names)) or rep not in names:
        raise ValueError("duplicate names or representative not among roster")
    sources = []
    for e in proof["evidence"]:
        if e["evidence_type"] != "complete_explicit_roster":
            continue
        if e["publication_status"] != "published" or not e["every_name_unique_same_term"]:
            raise ValueError("unpublished or identity-ambiguous official evidence")
        if e["representative"] != rep or set(e["all_names"]) != set(names):
            raise ValueError("conflicting official proposer rosters")
        m = meeting_by_id.get(e["meeting_id"])
        if not m or m["term"] != row["term"] or m["official_url"] != e["meeting_url"]:
            raise ValueError("meeting provenance/term does not agree")
        sources.append({
            "meeting_id": m["meeting_id"],
            "official_url": m["official_url"],
            "date": m["date"],
            "path": m["path"],
            "content_sha256": m["content_sha256"],
            "original_title_adjacent_evidence": e["source_excerpt"],
        })
    if not sources:
        raise ValueError("no source-backed explicit roster")
    result = dict(row)
    result.update({
        "representative_proposers": [rep],
        "co_proposers": [n for n in names if n != rep],
        "full_proposer_names": list(names),
        "proposer_roster_parse_status": "verified_official_minutes",
        "proposer_roster_repair_method": "exact_official_minutes_title_and_full_roster",
        "proposer_roster_minutes_evidence": sources,
        "proposer_roster_verified_at": stamp,
    })
    return result


def main(root=ROOT):
    items_path = root / "archive/bills/items.json"
    rows = load(items_path)
    if len(rows) != 3394:
        raise ValueError(f"unexpected baseline bill count: {len(rows)}")
    before = {str(x["internal_number"]): x for x in rows}
    evidence = recover(root)
    proposals = [
        r for r in evidence["records"]
        if r["status"] == "full_roster_evidenced_not_promoted"
    ]
    if len(proposals) != 17:
        raise ValueError(f"expected 17 strict source-backed rosters; got {len(proposals)}")
    if sum(len(r["verified_full_roster"]["all_names"]) for r in proposals) != 250:
        raise ValueError("unexpected proposer-list row count")
    by_id = {m["meeting_id"]: m for m in load(root / "indexes/integrated/meetings.json")}
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    changed = []
    replacements = {}
    for r in proposals:
        key = str(r["internal_number"])
        if key not in before:
            raise ValueError(f"missing bill id {key}")
        replacements[key] = promote_one(before[key], r, by_id, stamp)
        changed.append(key)

    new_items = [replacements.get(str(row["internal_number"]), row) for row in rows]
    assert len(new_items) == 3394
    # Preserve the original source data and new evidentiary snapshot.
    save_json(root / "reports/bill-minutes-proposer-evidence.json", evidence)
    save_json(items_path, new_items)

    link_report = link(root)
    audit_report = audit(root)
    remaining = audit_report["member_bills_without_names"]
    if len(remaining) != 8:
        raise ValueError(f"expected exactly 8 remaining incomplete rosters; found {len(remaining)}")
    if link_report["proposer_rows"] != 11408 or link_report["unresolved"] or link_report["ambiguous_same_term"]:
        raise ValueError(f"linked relation gate failed: {link_report}")
    if audit_report["nonmember_bills_with_person_names"] != 0:
        raise ValueError("institutional bills erroneously gained person names")
    bill_report_path = root / "reports/bills.json"
    bill_report = load(bill_report_path)
    bill_report.update({
        "checked_at": stamp,
        "records": len(new_items),
        "with_full_proposer_roster": sum(bool(r.get("full_proposer_names")) for r in new_items),
        "member_with_proposer_roster": audit_report["member_proposed_bills"] - len(remaining),
        "member_needing_minutes_fallback": len(remaining),
        "proposer_roster_status": "verified_full_source_rosters_with_remaining_exceptions",
    })
    save_json(bill_report_path, bill_report)

    repair_path = root / "reports/bill-proposer-repair.json"
    repair = load(repair_path)
    repair.update({
        "checked_at": stamp,
        "member_bills_with_names": audit_report["member_proposed_bills"] - len(remaining),
        "member_bills_without_names": len(remaining),
        "representative_rows": sum(len(x.get("representative_proposers") or []) for x in new_items),
        "co_proposer_rows": sum(len(x.get("co_proposers") or []) for x in new_items),
        "minutes_verified_member_bills": 17,
        "minutes_verified_proposer_rows": 250,
    })
    save_json(repair_path, repair)

    validate(root)
    manifest = export(root)
    if manifest["datasets"]["meetings"]["rows"] != 2339:
        raise ValueError("meeting export accidentally changed in row count")
    if manifest["datasets"]["bill_proposers"]["rows"] != 11408:
        raise ValueError("proposer export row count mismatch")
    result = {
        "checked_at": stamp,
        "status": "PASS",
        "baseline_member_without_roster": 25,
        "promoted_bills": len(changed),
        "promoted_proposer_relationships": 250,
        "promoted_internal_numbers": sorted(changed, key=int),
        "remaining_member_without_roster": len(remaining),
        "remaining_ids": sorted((str(x["internal_number"]) for x in remaining), key=int),
        "current_proposer_relationships": link_report["proposer_rows"],
        "exact_term_resolved": link_report["resolved_exact_term"],
        "unresolved_identity": link_report["unresolved"],
        "ambiguous_same_term": link_report["ambiguous_same_term"],
        "meetings_archive_unchanged_by_this_step": True,
        "source_only_export": manifest["principles"]["source_facts_only"],
    }
    save_json(root / "reports/bill-minutes-promotion.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
