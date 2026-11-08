"""Append verified analyzer exports to a reviewed Stage47 baseline."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re


def build(master, exports, commit, sequence=None):
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
    def bill_key(row):
        return row["term"], str(row.get("internal_number") or row.get("id"))

    occupied = {bill_key(row) for name in ("events", "review", "unlinked", "qa_cases")
                for row in model[name]}
    people = {row["person_id"]: row for row in model["people"]}
    links = defaultdict(list)
    for row in rows("bill_proposers_member_only"):
        if row.get("council_scope") == "cheongju_integrated":
            links[bill_key(row)].append(row)
    cutoff = bundle["source"]["manifest_generated_at"][:10]
    added_bills = 0
    bills = {}
    for row in rows("bills"):
        if row.get("council_scope") != "cheongju_integrated":
            continue
        key = bill_key(row)
        if key in bills:
            raise ValueError(f"Duplicate source bill: {key}")
        bills[key] = {field: row.get(field) for field in (
            "term", "internal_number", "title", "proposal_date", "bill_type",
            "official_url", "proposer_type", "proposer_type_list",
        )}
        # Historical omissions stay in the inventory. Existing reviews retain precedence.
        date = row.get("proposal_date") or ""
        if key in occupied or date <= cutoff or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            continue
        if not row.get("detail_text_checked"):
            continue
        declared = {
            "representative": row.get("representative_proposers") or [],
            "co_proposer": row.get("co_proposers") or [],
        }
        expected = [(role, name) for role, names in declared.items() for name in names]
        roster = links[key]
        actual = [(link["proposer_role"], link["person_name"]) for link in roster]
        if (not declared["representative"] or len(expected) < 2
                or sorted(actual) != sorted(expected)
                or len({name for _, name in expected}) != len(expected)):
            continue
        roles = {link["person_id"]: link["proposer_role"] for link in roster}
        if len(roles) != len(roster) or any(
            link["resolution_status"] != "resolved_exact_term"
            or people.get(link["person_id"], {}).get("term") != key[0]
            or people[link["person_id"]]["name"] != link["person_name"]
            or people[link["person_id"]].get("scope") != "cheongju_integrated"
            for link in roster
        ):
            continue
        model["events"].append({
            "term": key[0], "internal_number": key[1], "title": row["title"],
            "date": date, "bill_type": row.get("bill_type"), "official_url": row["official_url"],
            "member_ids": list(roles), "roles": roles, "member_count": len(roles),
            "representative_count": len(declared["representative"]),
            "roster_names": [name for _, name in expected],
            "representative_names": declared["representative"],
            "stage38_status": "archive_exact_term_and_roster",
        })
        added_bills += 1
    model["summary"].update(events=len(model["events"]),
                            sum_members=sum(row["member_count"] for row in model["events"]))
    counts["bills_linked"] = added_bills
    attachments = {}
    for row in rows("research_attachments"):
        url = row["official_url"]
        if not re.match(r"^https://council(?:rec)?\.cheongju\.go\.kr/", url):
            raise ValueError(f"Unexpected attachment origin: {url}")
        key = (row["parent_type"], row["parent_id"], url)
        attachments[key] = {field: row.get(field) for field in (
            "parent_type", "parent_id", "title", "official_url", "file_type",
        )}
    bundle["source"]["incremental_inventory"] = {
        "bills": list(bills.values()), "research_attachments": list(attachments.values()),
    }
    counts.update(bill_inventory=len(bills), research_attachment_inventory=len(attachments))
    if sequence is not None and sequence <= bundle["sequence"]:
        raise ValueError("Release sequence must exceed baseline")
    bundle["sequence"] = sequence if sequence is not None else bundle["sequence"] + 1
    bundle["release_id"] = f"stage47-{bundle['sequence']}-{commit[:12]}"
    bundle["source"]["incremental_archive_commit"] = commit
    return bundle, counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master", type=Path)
    parser.add_argument("exports", type=Path)
    parser.add_argument("archive_commit")
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--sequence", type=int)
    args = parser.parse_args()
    bundle, counts = build(args.master.read_text(encoding="utf-8"), args.exports, args.archive_commit, args.sequence)
    with args.candidate.open("x", encoding="utf-8") as out:
        json.dump(bundle, out, ensure_ascii=False, separators=(",", ":"))
    print(json.dumps(counts))
