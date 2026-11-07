"""Append verified analyzer exports to a reviewed Stage47 baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def build(master, exports, commit):
    baseline = re.search(r'<script id="release-bundle" type="application/json">(.*?)</script>', master, re.S)
    if not baseline or not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid master HTML or archive commit")
    bundle = json.loads(baseline[1])
    if bundle["audience"]["kind"] != "master":
        raise ValueError("A Stage47 master baseline is required")
    model = bundle["model"]
    manifest = json.loads((exports / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema"] != "cheongju-council-archive-analyzer-export/0.1":
        raise ValueError("Unsupported analyzer export schema")

    def rows(name):
        data = (exports / (name + ".jsonl")).read_bytes()
        entry = manifest["datasets"][name]
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"{name}: export digest mismatch")
        records = [json.loads(line) for line in data.splitlines()]
        if len(records) != entry["rows"]:
            raise ValueError(f"{name}: export row count mismatch")
        return records

    counts = {}
    meeting_fields = ("meeting_id", "term", "title", "date", "publication_status",
                      "official_url", "path", "sha256", "content_sha256")
    meetings = {r["meeting_id"]: r for r in model["meeting_inventory"]}
    before = meetings.copy()
    for row in rows("meetings"):
        if row["council_scope"] == "cheongju_integrated":
            meetings[row["meeting_id"]] = {key: row.get(key) for key in meeting_fields}
    model["meeting_inventory"] = list(meetings.values())
    counts["meetings"] = sum(before.get(key) != row for key, row in meetings.items())

    activities = {r["activity_id"]: r for r in model["activities"]}
    for kind in ("five_minute_speeches", "city_questions", "written_questions"):
        counts[kind] = 0
        for row in rows(kind):
            if row.get("council_scope") != "cheongju_integrated":
                continue
            key = f"{kind}:{row['source_id']}"
            if key in activities:
                continue
            activities[key] = {
                **{field: row.get(field) for field in ("date", "speaker_name",
                   "question_file_url", "answer_file_url", "checked_at")},
                "official_url": row.get("official_url") or row.get("detail_url"),
                "activity_id": key, "source_id": str(row["source_id"]), "kind": kind,
                "source_dataset": kind, "title": row.get("title") or row.get("title_list") or "",
                "body_text": row.get("body_text") or "", "attachments": row.get("attachments") or [],
                "person_id": None, "term": None, "identity_evidence": None,
                "identity_status": "unresolved_no_unique_dated_tenure",
            }
            counts[kind] += 1
    model["activities"] = list(activities.values())
    linked = sum(bool(r["person_id"]) for r in activities.values())
    model["activity_coverage"].update(source_rows=len(activities), identity_resolved=linked,
                                      identity_unresolved=len(activities)-linked,
                                      meeting_index_rows=len(meetings))
    bundle["sequence"] += 1
    bundle["release_id"] = f"stage47-{bundle['sequence']}-{commit[:12]}"
    bundle["source"]["incremental_archive_commit"] = commit
    return bundle, counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master", type=Path)
    parser.add_argument("exports", type=Path)
    parser.add_argument("archive_commit")
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    bundle, counts = build(args.master.read_text(encoding="utf-8"), args.exports, args.archive_commit)
    with args.candidate.open("x", encoding="utf-8") as out:
        json.dump(bundle, out, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(counts))
