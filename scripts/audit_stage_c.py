"""Read-only, offline integrity audit of the integrated meeting archive (Stage C).

Checks the stored index, per-term shards, Markdown bodies, and exported JSONL.
It does not access the official website and does not mutate source data.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCOPE = "cheongju_integrated"
STATUSES = {"published", "provisional", "superseded"}
TERMS = (1, 2, 3, 4)
SOURCE_URL = "https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canon(text):
    return re.sub(r"\s+", " ", text).strip()


def markdown_parts(text):
    """Return preserved title, metadata and original source body, when possible."""
    pieces = text.split("\n\n", 2)
    if len(pieces) != 3 or not pieces[0].startswith("# "):
        raise ValueError("unexpected markdown header/body layout")
    title, header, rendered_body = pieces
    metadata = {}
    for line in header.splitlines():
        if not line.startswith("- ") or ": " not in line:
            raise ValueError("malformed provenance header")
        key, value = line[2:].split(": ", 1)
        metadata[key] = value
    # Collector writes one newline after the official body, and converts
    # official speaker lines from '○' to markdown '## ○'.
    body = re.sub(r"(?m)^## ○", "○", rendered_body.removesuffix("\n"))
    return title[2:], metadata, body


def audit(root=ROOT):
    root = Path(root)
    errors, warnings = [], []
    summary = {
        "scope": "offline stored snapshot (not a fresh official-site inventory)",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": None,
        "source_rows": 0,
        "source_files_checked": 0,
        "source_file_bytes_checked": 0,
        "sha256_file_verified": 0,
        "sha256_content_verified": 0,
        "export_rows_checked": 0,
        "export_files_hash_verified": 0,
        "published": 0,
        "provisional": 0,
        "superseded": 0,
        "by_term": {},
        "year_inventory_only_term": [],
        "errors": errors,
        "warnings": warnings,
    }

    index_path = root / "indexes/integrated/meetings.json"
    manifest_path = root / "exports/analyzer/manifest.json"
    sync_path = root / "reports/integrated-sync.json"
    history_path = root / "indexes/integrated/meeting_history.json"
    if not index_path.is_file() or not manifest_path.is_file() or not sync_path.is_file():
        errors.append("missing one of canonical index, export manifest, or sync report")
        summary["status"] = "FAIL"
        return summary

    rows = read_json(index_path)
    sync = read_json(sync_path)
    manifest = read_json(manifest_path)
    history = read_json(history_path) if history_path.is_file() else []
    if not isinstance(rows, list):
        errors.append("canonical meeting index must be a list")
        summary["status"] = "FAIL"
        return summary
    if not isinstance(history, list):
        errors.append("meeting history must be a list")
        history = []

    summary["source_rows"] = len(rows)
    by_id = {}
    ids_by_term = collections.defaultdict(set)
    referenced_paths = set()

    for idx, row in enumerate(rows):
        prefix = f"row #{idx}"
        mid, sid = row.get("meeting_id"), str(row.get("source_id", ""))
        if not mid or mid in by_id:
            errors.append(f"{prefix}: duplicate/blank meeting_id {mid!r}")
            continue
        by_id[mid] = row
        term = row.get("term")
        if term not in TERMS:
            errors.append(f"{mid}: unexpected council term {term!r}")
            continue
        ids_by_term[term].add(mid)
        if row.get("council_scope") != SCOPE:
            errors.append(f"{mid}: unexpected council scope")
        if mid != f"{SCOPE}:minutes-{sid}" or not sid.isdigit():
            errors.append(f"{mid}: source_id does not match meeting_id")
        if row.get("legacy_minutes_id") != f"minutes-{sid}":
            errors.append(f"{mid}: legacy_minutes_id mismatch")
        status = row.get("publication_status")
        if status not in {"published", "provisional"}:
            errors.append(f"{mid}: invalid current publication status {status!r}")
        if row.get("official_url") != SOURCE_URL + sid:
            errors.append(f"{mid}: official_url/source_id mismatch")
        date = str(row.get("date", ""))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            errors.append(f"{mid}: invalid date {date!r}")
            continue
        if row.get("year") != int(date[:4]):
            errors.append(f"{mid}: year and date disagree")
        expected_path = f"archive/meetings/{SCOPE}/term-{term}/{date[:4]}/minutes-{sid}.md"
        relpath = row.get("path")
        if relpath != expected_path:
            errors.append(f"{mid}: path differs from term/year/source_id")
            continue
        if relpath in referenced_paths:
            errors.append(f"{mid}: duplicate file path {relpath}")
        referenced_paths.add(relpath)
        path = root / expected_path
        if not path.is_file():
            errors.append(f"{mid}: missing Markdown file")
            continue
        raw = path.read_bytes()
        summary["source_files_checked"] += 1
        summary["source_file_bytes_checked"] += len(raw)
        if row.get("bytes") != len(raw):
            errors.append(f"{mid}: byte size mismatch index={row.get('bytes')} actual={len(raw)}")
        if row.get("sha256") != sha256(raw):
            errors.append(f"{mid}: Markdown SHA-256 mismatch")
        else:
            summary["sha256_file_verified"] += 1
        try:
            title, metadata, body = markdown_parts(raw.decode("utf-8"))
        except (UnicodeError, ValueError) as ex:
            errors.append(f"{mid}: invalid Markdown/body: {ex}")
            continue
        header_fields = {
            "official_url": row.get("official_url"),
            "meeting_date": date,
            "source_id": sid,
            "council_scope": SCOPE,
            "term": str(term),
            "publication_status": status,
            "collected_at": row.get("first_seen_at"),
        }
        for field, expected in header_fields.items():
            if metadata.get(field) != expected:
                errors.append(f"{mid}: provenance header {field} mismatch")
        if title != row.get("title"):
            errors.append(f"{mid}: Markdown title mismatch")
        if row.get("content_sha256") != sha256(canon(body).encode("utf-8")):
            errors.append(f"{mid}: canonical official body SHA-256 mismatch")
        else:
            summary["sha256_content_verified"] += 1
        if len(canon(body)) < 100 and "개의되지 않음" not in body:
            errors.append(f"{mid}: body unexpectedly short ({len(canon(body))} chars)")
        if len(canon(body)) < 300 and "개의되지 않음" not in body:
            warnings.append(f"{mid}: body shorter than 300 chars")
        if "## ○" not in raw.decode("utf-8") and "개의되지 않음" not in body:
            warnings.append(f"{mid}: no speaker heading in preserved Markdown")
        if row.get("inventory_sources") not in (["term"], ["term", "year"]):
            errors.append(f"{mid}: unexpected inventory source labels")
        if not row.get("first_seen_at") or not row.get("last_checked_at"):
            errors.append(f"{mid}: missing collection timestamps")

    summary["by_term"] = {str(term): len(ids_by_term[term]) for term in TERMS}
    summary["published"] = sum(r.get("publication_status") == "published" for r in rows)
    summary["provisional"] = sum(r.get("publication_status") == "provisional" for r in rows)
    summary["superseded"] = len(history)

    shard_ids = set()
    for term in TERMS:
        shard_path = root / f"indexes/integrated/initial_term_{term}.json"
        if not shard_path.is_file():
            errors.append(f"missing term {term} shard")
            continue
        shard = read_json(shard_path)
        if not isinstance(shard, list):
            errors.append(f"term {term} shard is not an array")
            continue
        local_ids = set()
        for row in shard:
            mid = row.get("meeting_id")
            if mid in local_ids or mid in shard_ids:
                errors.append(f"duplicate meeting ID in shard {term}: {mid}")
            local_ids.add(mid)
            shard_ids.add(mid)
            if row.get("term") != term:
                errors.append(f"{mid}: shard term disagrees")
            if by_id.get(mid) != row:
                errors.append(f"{mid}: shard row and canonical row differ")
        if local_ids != ids_by_term[term]:
            errors.append(f"term {term} shard ID set != canonical index")
        term_report_path = root / f"reports/integrated-initial-term-{term}.json"
        if term_report_path.exists():
            report = read_json(term_report_path)
            if report.get("listed") != len(local_ids):
                errors.append(f"term {term} report count mismatch")

    if shard_ids != set(by_id):
        errors.append("canonical meeting ID set != union of term shards")

    for row in history:
        mid = row.get("meeting_id")
        if mid in by_id:
            errors.append(f"historical superseded meeting still current: {mid}")
        if row.get("publication_status") != "superseded":
            errors.append(f"meeting_history contains non-superseded record: {mid}")
        if not row.get("superseded_by"):
            errors.append(f"historical meeting without replacement: {mid}")
        if row.get("path"):
            referenced_paths.add(row["path"])

    all_files = {
        path.relative_to(root).as_posix()
        for path in (root / "archive/meetings/cheongju_integrated").glob("term-*/*/minutes-*.md")
    }
    if all_files != referenced_paths:
        for rel in sorted(referenced_paths - all_files)[:50]:
            errors.append(f"referenced but absent Markdown file: {rel}")
        for rel in sorted(all_files - referenced_paths)[:50]:
            errors.append(f"unindexed Markdown file: {rel}")
        if len(all_files ^ referenced_paths) > 100:
            errors.append(f"total orphan/missing paths={len(all_files ^ referenced_paths)}")

    if sync.get("listed") != len(rows):
        errors.append("integrated-sync listed count mismatch")
    for key in ("published", "provisional"):
        if sync.get(key) != summary[key]:
            errors.append(f"integrated-sync {key} count mismatch")
    if sync.get("history_rows") != len(history):
        errors.append("integrated-sync history count mismatch")
    for term in TERMS:
        if sync.get("by_term", {}).get(str(term)) != len(ids_by_term[term]):
            errors.append(f"integrated-sync term {term} count mismatch")

    qa = sync.get("inventory_qa", {})
    only_term = sorted(
        (r for r in rows if r.get("inventory_sources") == ["term"]),
        key=lambda r: int(r["source_id"]),
    )
    summary["year_inventory_only_term"] = [
        {
            "source_id": r["source_id"],
            "term": r["term"],
            "date": r["date"],
            "status": r["publication_status"],
            "title": r["title"],
            "official_url": r["official_url"],
        }
        for r in only_term
    ]
    if set(qa.get("only_term", [])) != {r["source_id"] for r in only_term}:
        errors.append("13 term-only inventory IDs differ from stored report")
    if qa.get("term_inventory_count") != len(rows):
        errors.append("term inventory count mismatch")
    if qa.get("year_inventory_count") != len(rows) - len(only_term):
        errors.append("year inventory count mismatch (only_year must be empty)")
    if qa.get("only_year"):
        warnings.append("year inventory has year-only rows; term assignment requires manual review")

    manifest_datasets = manifest.get("datasets", {})
    for name, item in manifest_datasets.items():
        rel = item.get("path")
        if not rel or not rel.startswith("exports/analyzer/") or ".." in Path(rel).parts:
            errors.append(f"invalid export path: {name}")
            continue
        export_file = root / rel
        if not export_file.is_file():
            errors.append(f"missing export file: {name}")
            continue
        digest = hashlib.sha256()
        count = 0
        with export_file.open("rb") as fd:
            for line in fd:
                digest.update(line)
                if line.strip():
                    count += 1
                    if name == "meetings":
                        try:
                            exported = json.loads(line)
                        except ValueError:
                            errors.append(f"invalid meeting JSONL row {count}")
                            continue
                        if count > len(rows) or exported != rows[count - 1]:
                            errors.append(f"meeting export diverges from index at row {count}")
        if digest.hexdigest() != item.get("sha256"):
            errors.append(f"manifest sha256 mismatch: {name}")
        else:
            summary["export_files_hash_verified"] += 1
        if item.get("rows") != count:
            errors.append(f"manifest row count mismatch: {name}")
        if name == "meetings":
            summary["export_rows_checked"] = count
            if count != len(rows):
                errors.append("meeting export has different number of rows")
    if "meetings" not in manifest_datasets:
        errors.append("meeting export absent from analyzer manifest")
    if not manifest.get("principles", {}).get("source_facts_only"):
        errors.append("manifest lacks source-only provenance principle")
    summary["status"] = "FAIL" if errors else "PASS"
    summary["error_count"] = len(errors)
    summary["warning_count"] = len(warnings)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/stage-c-offline-audit.json")
    args = parser.parse_args()
    result = audit(ROOT)
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    brief = {key: result[key] for key in (
        "status", "source_rows", "source_files_checked",
        "sha256_file_verified", "sha256_content_verified",
        "export_rows_checked", "export_files_hash_verified",
        "published", "provisional", "by_term", "error_count", "warning_count"
    )}
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    for error in result["errors"][:30]:
        print("ERROR:", error)
    if len(result["errors"]) > 30:
        print("ERROR: additional errors in report:", len(result["errors"]) - 30)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
