"""Read-only schema and safe-join preflight of an existing single-file analyzer HTML.

This is not a migration: it never updates or reclassifies the user's analyzer.
It deliberately prohibits person-name/title-only joins to the official archive.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

DATA_TAG = re.compile(r'<script\b(?=[^>]*\bid=["\']cca-data["\'])[^>]*>(.*?)</script\s*>', re.I | re.S)


class AnalyzerPreflightError(ValueError):
    """An input structure cannot safely be audited."""


def _object_list(payload: dict, name: str) -> list[dict]:
    value = payload.get(name)
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise AnalyzerPreflightError("Missing or non-object list: " + name)
    return value


def inspect_html(path: Path, archive_manifest: Path | None = None) -> dict:
    """Inspect legacy analyzer data; return facts, blockers and QA results only."""
    path = Path(path)
    content = path.read_bytes()
    if len(content) > 160_000_000:
        raise AnalyzerPreflightError("Analyzer HTML exceeds bounded input size")
    try:
        doc = content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise AnalyzerPreflightError("Analyzer HTML is not UTF-8") from exc
    match = DATA_TAG.search(doc)
    if not match:
        raise AnalyzerPreflightError("Embedded cca-data JSON not found")
    try:
        data = json.loads(match.group(1))
    except ValueError as exc:
        raise AnalyzerPreflightError("Invalid embedded JSON") from exc
    if not isinstance(data, dict):
        raise AnalyzerPreflightError("Embedded data is not a JSON object")
    meta = data.get("meta") or {}
    if meta.get("schema") != "cheongju-integrated-html-embedded-data/1.0":
        raise AnalyzerPreflightError("Unsupported analyzer HTML data schema")
    facts = _object_list(data, "facts")
    links = _object_list(data, "member_fact_links")
    ids = [str(row.get("fact_id") or "") for row in facts]
    if not all(ids) or len(ids) != len(set(ids)):
        raise AnalyzerPreflightError("Missing/duplicate normalized fact ID")
    idset = set(ids)
    orphans = [str(row.get("fact_id") or "") for row in links if str(row.get("fact_id") or "") not in idset]
    if orphans:
        raise AnalyzerPreflightError(f"Orphan member_fact_links: {len(orphans)}")
    bill_facts = [row for row in facts if row.get("domain") == "BILLS"]
    bill_ids = {row["fact_id"] for row in bill_facts}
    bill_links = [row for row in links if row.get("fact_id") in bill_ids]
    src_ids = [(row.get("source_ref") or {}).get("source_item_id") for row in bill_facts]
    if any(not value for value in src_ids) or len(src_ids) != len(set(src_ids)):
        raise AnalyzerPreflightError("Missing/duplicate old analyzer source item ID")
    # Neither a title nor an opaque source_item_id is the official bill internal number.
    official_keys = sum(bool(row.get("internal_number")) for row in bill_facts)
    actor_labels = sum(bool(row.get("proposer_type") or row.get("proposer_type_list")) for row in bill_facts)
    roles = sum(bool(row.get("proposer_role")) for row in bill_links)
    join_safe = official_keys == len(bill_facts) and actor_labels == len(bill_facts) and roles == len(bill_links) and bool(bill_facts)
    report = {
        "status": "STRUCTURAL_PASS_CROSSWALK_NOT_VERIFIED" if not join_safe else "STRUCTURAL_PASS_ID_FIELDS_PRESENT_UNVERIFIED",
        "read_only": True,
        "source_modified": False,
        "file_sha256": hashlib.sha256(content).hexdigest(),
        "file_bytes": len(content),
        "analyzer_meta": meta,
        "normalized_fact_count": len(facts),
        "member_fact_links_count": len(links),
        "normalized_bill_fact_count": len(bill_facts),
        "bill_member_fact_links_count": len(bill_links),
        "bill_facts_with_at_least_one_member_link": len({row["fact_id"] for row in bill_links}),
        "bill_facts_with_member_contexts": sum(bool(row.get("member_contexts")) for row in bill_facts),
        "bill_facts_with_official_internal_number": official_keys,
        "bill_facts_with_proposer_type_fields": actor_labels,
        "bill_member_links_with_proposer_role": roles,
        "bill_facts_with_official_url": sum(bool(row.get("official_url")) for row in bill_facts),
        "bill_source_id_kind": "opaque source_item_id; not official internal_number",
        "bill_scope_values": dict(collections.Counter(row.get("council_scope") for row in bill_facts)),
        "bill_date_min": min((str(row["date"]) for row in bill_facts if row.get("date")), default=None),
        "bill_date_max": max((str(row["date"]) for row in bill_facts if row.get("date")), default=None),
        "official_archive_join_authorized": False,
        "external_current_pc_version_verified": False,
        "direct_person_identity_merge_authorized": False,
        "blockers": [
            "No validated official internal-number to legacy source_item_id crosswalk",
            "No verified same-term archive person-ID to analyzer member-ID crosswalk",
            "No proposer-role provenance in old member_fact_links; cannot classify old BILLS counts as representative/co-proposal counts",
            "Different snapshots and scope spellings require explicit version/scope normalization",
            "Matching titles, dates or member names alone cannot authorize a join",
        ],
    }
    if archive_manifest is not None:
        try:
            m = json.loads(Path(archive_manifest).read_text("utf-8"))
            datasets = m["datasets"]
            if m.get("schema") != "cheongju-council-archive-analyzer-export/0.1":
                raise ValueError("invalid archive schema")
            approved = m.get("principles", {}).get("personal_proposer_statistics_dataset")
            if approved != "bill_proposers_member_only":
                raise ValueError("unsafe personal proposer dataset")
            report["archive_manifest_baseline"] = {
                "schema": m["schema"], "generated_at": m.get("generated_at"),
                "bills": datasets["bills"]["rows"],
                "raw_relationships": datasets["bill_proposers"]["rows"],
                "member_only_relationships": datasets[approved]["rows"],
                "institutional_quarantine_relationships": datasets["bill_proposers_institutional_type_quarantine"]["rows"],
                "counts_are_non_equivalent_due_to_old_snapshot_and_different_semantics": True,
            }
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise AnalyzerPreflightError("Invalid external archive manifest") from exc
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="Read-only path to an existing integrated analyzer HTML")
    parser.add_argument("--archive-manifest", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(inspect_html(args.html, args.archive_manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
