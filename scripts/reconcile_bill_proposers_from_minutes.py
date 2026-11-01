"""Strict official-meeting proposer evidence for missing bill rosters.

No source-site HTTP, no archive mutation, no automatic identity promotion.
Only '(홍길동 의원 대표발의)(홍길동, ... 의원 발의)' immediately
after the exact bill title qualifies as a *full* proposer roster.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import re
from pathlib import Path

from find_bill_minutes_fallback import compact, compact_with_indices, near_day, session_match
from link_bill_proposers import build_term_name_index

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/bill-minutes-proposer-evidence.json"
FULL = re.compile(
    r"^\s*\(\s*([가-힣]{2,4})\s*의원\s*대표\s*발의\s*\)"
    r"\s*\(\s*([^()]{2,850})\s*\)", re.S
)
ROSTER = re.compile(r"^([가-힣,\s·ㆍ]+?)\s*의원\s*발의\s*$", re.S)
REP_BACK = [
    re.compile(r"([가-힣]{2,4})\s*의원님?이\s*대표\s*발의하신\s*$"),
    re.compile(r"([가-힣]{2,4})\s*의원\s*등\s*[가-힣0-9\s]{1,16}분(?:의\s*의원)?으로부터\s*발의된\s*$"),
    re.compile(r"([가-힣]{2,4})\s*의원\s*외\s*[가-힣0-9\s]{1,16}분으로부터\s*발의된\s*$"),
]


def parse_full_roster(after):
    """Return representative and all listed proposers only for exact syntax."""
    m = FULL.match(after)
    if not m:
        return None
    parsed = ROSTER.fullmatch(m[2].strip())
    if not parsed:
        return None
    text = parsed[1].strip()
    chunks = [re.sub(r"\s+", "", x) for x in re.split("[,·ㆍ]", text)]
    if (not chunks or not all(re.fullmatch(r"[가-힣]{2,4}", n) for n in chunks)
            or len(chunks) != len(set(chunks)) or m[1] not in chunks):
        return None
    return {"representative": m[1], "all_names": chunks, "evidence_text": m[0].strip()}


def parse_representative_before(before):
    tail = before[-100:]
    for rule in REP_BACK:
        m = rule.search(tail)
        if m:
            return {"representative": m[1], "source_fragment": tail[max(0,m.start()-10):]}
    return None


def search_minutes_for_bill(bill, meetings, root, person_index, body_cache):
    term = int(bill["term"])
    title_normalized = compact(bill["title"])
    records = []
    for meeting in meetings:
        if meeting.get("term") != term:
            continue
        if not session_match(bill.get("session"), meeting.get("title")):
            continue
        if not near_day(meeting.get("date"), bill.get("proposal_date"), bill.get("processed_date")):
            continue
        relative = meeting["path"]
        if relative not in body_cache:
            raw = (root / relative).read_text(encoding="utf-8")
            body = raw.split("\n\n", 2)[2]
            body_cache[relative] = (body, *compact_with_indices(body))
        body, normalized, offsets = body_cache[relative]
        start = 0
        for i in range(30):
            at = normalized.find(title_normalized, start)
            if at < 0:
                break
            start = at + len(title_normalized)
            if not title_normalized:
                continue
            pos = offsets[at]
            end = offsets[at + len(title_normalized) - 1] + 1
            after = body[end:end+1100]
            before = body[max(0, pos-120):pos]
            full = parse_full_roster(after)
            rep_only = parse_representative_before(before)
            if not full and not rep_only:
                continue
            names = full["all_names"] if full else [rep_only["representative"]]
            identities = [
                {"name": name, "person_ids": person_index.get(term, {}).get(name, [])}
                for name in names
            ]
            record = {
                "meeting_id": meeting["meeting_id"],
                "meeting_date": meeting["date"],
                "meeting_url": meeting["official_url"],
                "source_path": relative,
                "publication_status": meeting["publication_status"],
                "evidence_type": "complete_explicit_roster" if full else "representative_only",
                "representative": full["representative"] if full else rep_only["representative"],
                "all_names": full["all_names"] if full else None,
                "source_excerpt": (
                    bill["title"] + full["evidence_text"]
                    if full else rep_only["source_fragment"] + bill["title"]
                ),
                "identity_matches": identities,
                "every_name_unique_same_term": all(len(x["person_ids"]) == 1 for x in identities),
            }
            records.append(record)
    return records


def recover(root=ROOT):
    missing = json.loads((root/"reports/bill-data-audit.json").read_text(encoding="utf-8"))["member_bills_without_names"]
    meetings = json.loads((root/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
    if len(missing) != 25:
        raise ValueError(f"Snapshot expected 25 missing member bills, found {len(missing)}")
    persons = build_term_name_index(root)
    cache = {}
    results = []
    for bill in missing:
        evidence = search_minutes_for_bill(bill, meetings, root, persons, cache)
        complete = [x for x in evidence if x["evidence_type"] == "complete_explicit_roster"]
        signatures = { (x["representative"], tuple(sorted(x["all_names"]))) for x in complete }
        fully_valid = (
            bool(complete) and len(signatures) == 1
            and all(x["every_name_unique_same_term"] and x["publication_status"] == "published" for x in complete)
        )
        representative_candidates = sorted({x["representative"] for x in evidence})
        if fully_valid:
            status = "full_roster_evidenced_not_promoted"
        elif len(signatures) > 1:
            status = "conflicting_explicit_rosters_manual_review"
        elif complete:
            status = "full_roster_identity_or_publication_review"
        elif len(representative_candidates) == 1:
            status = "representative_only_not_full_roster"
        elif representative_candidates:
            status = "representative_conflict_manual_review"
        else:
            status = "no_explicit_proposer_evidence"
        results.append({
            "internal_number": bill["internal_number"],
            "term": bill["term"],
            "bill_number": bill.get("bill_number"),
            "title": bill["title"],
            "session": bill.get("session"),
            "proposal_date": bill.get("proposal_date"),
            "official_bill_url": bill.get("official_url"),
            "status": status,
            "representatives_mentioned": representative_candidates,
            "verified_full_roster": (
                {
                    "representative": complete[0]["representative"],
                    "all_names": complete[0]["all_names"],
                    "proposer_count": len(complete[0]["all_names"]),
                } if fully_valid else None
            ),
            "evidence": evidence,
        })
    counts = dict(collections.Counter(x["status"] for x in results))
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "method": "exact term+session+date and direct title-adjacent source text",
        "complete_explicit_roster": counts.get("full_roster_evidenced_not_promoted", 0),
        "no_auto_promotions": True,
        "records": results,
        "status_counts": counts,
        "notes": [
            "Only official meeting source text is considered evidence.",
            "Each full-roster name must resolve uniquely in the same council term.",
            "Representative-only evidence must never be treated as complete co-proposer list.",
            "A bill may have separate later amendments; only title-adjacent original proposal is matched.",
            "No canonical bill archive/identity/export data is changed by this script.",
        ],
    }
    return report


if __name__ == "__main__":
    result = recover(ROOT)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "complete_explicit_roster": result["complete_explicit_roster"],
        "status_counts": result["status_counts"],
        "missing_bills": [
            {"internal_number": r["internal_number"], "status": r["status"],
             "representative": (r["verified_full_roster"] or {}).get("representative"),
             "proposer_count": (r["verified_full_roster"] or {}).get("proposer_count")}
            for r in result["records"]
        ],
    }, ensure_ascii=False, indent=2))
