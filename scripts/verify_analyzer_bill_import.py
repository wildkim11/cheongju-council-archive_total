"""Fail-closed, read-only loader for the personal bill-proposer analyzer dataset.

This validates the archive producer's manifest and exact lossless partition.
It is an integration boundary, not evidence that an external analyzer uses it.
No archive data, manifest, or export file is written by this module.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cheongju-council-archive-analyzer-export/0.1"
SAFE = "bill_proposers_member_only"
RAW = "bill_proposers"
QUARANTINE = "bill_proposers_institutional_type_quarantine"
REQUIRED = ("bills", RAW, SAFE, QUARANTINE)


class UnsafeBillImport(ValueError):
    """Source/manifest mismatches must stop downstream personal statistics."""


def _read_manifest(root: Path) -> dict:
    try:
        manifest = json.loads((root / "exports/analyzer/manifest.json").read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise UnsafeBillImport("Missing or invalid analyzer manifest") from exc
    if manifest.get("schema") != SCHEMA:
        raise UnsafeBillImport("Unsupported analyzer export schema")
    principles = manifest.get("principles") or {}
    if (principles.get("source_facts_only") is not True
            or principles.get("analysis_judgments_included") is not False
            or principles.get("personal_proposer_statistics_dataset") != SAFE
            or principles.get("institutional_type_person_names_quarantined_dataset") != QUARANTINE):
        raise UnsafeBillImport("Manifest does not authorize the safe proposer dataset")
    if any(x not in manifest.get("datasets", {}) for x in REQUIRED):
        raise UnsafeBillImport("Required bill datasets are absent; refusing raw fallback")
    return manifest


def _verified_jsonl(root: Path, info: dict, expected_name: str) -> list[dict]:
    export_dir = (root / "exports/analyzer").resolve()
    expected_path = export_dir / (expected_name + ".jsonl")
    relative = info.get("path", "")
    if not isinstance(relative, str) or relative.replace("\\", "/") != "exports/analyzer/" + expected_name + ".jsonl":
        raise UnsafeBillImport("Unexpected dataset path: " + expected_name)
    path = (root / relative).resolve()
    if path != expected_path:
        raise UnsafeBillImport("Unsafe dataset path: " + expected_name)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise UnsafeBillImport("Missing dataset: " + expected_name) from exc
    digest = info.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise UnsafeBillImport("Invalid digest in manifest: " + expected_name)
    if hashlib.sha256(raw_bytes).hexdigest() != digest:
        raise UnsafeBillImport("SHA-256 mismatch: " + expected_name)
    try:
        lines = raw_bytes.decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines]
    except (UnicodeError, ValueError) as exc:
        raise UnsafeBillImport("Non-UTF-8 or invalid JSONL: " + expected_name) from exc
    if not all(isinstance(row, dict) for row in rows):
        raise UnsafeBillImport("Non-object JSONL record: " + expected_name)
    if not isinstance(info.get("rows"), int) or len(rows) != info["rows"]:
        raise UnsafeBillImport("Manifest row-count mismatch: " + expected_name)
    return rows


def _personal_bill(bill: dict) -> bool:
    list_type = str(bill.get("proposer_type_list") or "").strip()
    detail_type = str(bill.get("proposer_type") or "").strip()
    return (list_type == "의원" or detail_type == "의원") and not (
        list_type and detail_type and list_type != detail_type
    )


def load_verified_personal_proposers(root: Path = ROOT) -> tuple[list[dict], dict]:
    """Return ONLY safe person links after manifest, hash and partition QA.

    Never silently substitute RAW when SAFE is missing. An unverified roster
    stays unverified; using the safe view does not fill missing co-proposers.
    """
    root = Path(root).resolve()
    manifest = _read_manifest(root)
    rows = {
        name: _verified_jsonl(root, manifest["datasets"][name], name)
        for name in REQUIRED
    }
    bills = {}
    for bill in rows["bills"]:
        key = str(bill.get("internal_number") or "")
        if not key or key in bills:
            raise UnsafeBillImport("Missing/duplicate bill internal_number")
        bills[key] = bill
    expected_safe, expected_quarantine = [], []
    for link in rows[RAW]:
        key = str(link.get("internal_number") or "")
        if key not in bills:
            raise UnsafeBillImport("Person link refers to an unknown bill: " + key)
        if _personal_bill(bills[key]):
            expected_safe.append(link)
        else:
            expected_quarantine.append(link)
    if rows[SAFE] != expected_safe or rows[QUARANTINE] != expected_quarantine:
        raise UnsafeBillImport("Source relationships are lost, reordered, or misclassified")
    return rows[SAFE], {
        "status": "PASS",
        "source_bills": len(bills),
        "raw_links": len(rows[RAW]),
        "safe_member_links": len(rows[SAFE]),
        "quarantined_links": len(rows[QUARANTINE]),
        "personal_proposer_statistics_dataset": SAFE,
        "external_analyzer_connection_verified": False,
        "source_files_modified": False,
    }


if __name__ == "__main__":
    _, summary = load_verified_personal_proposers()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
