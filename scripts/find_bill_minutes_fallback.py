"""Find *candidate* official minutes for 25 bills with missing proposer rosters.

Offline audit. Does not modify bills, identities, proposer relationships, or source
minutes. A title mention is NOT evidence of authorship; output requires review.
"""
from __future__ import annotations
import collections
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports/bill-data-audit.json"
INDEX = ROOT / "indexes/integrated/meetings.json"
OUTPUT = ROOT / "reports/bill-minutes-fallback-candidates.json"
NAME = re.compile(r"(?<![가-힣])([가-힣]{2,4})\s*(?:의원|위원장|의장)(?![가-힣])")
SPEAKER = re.compile(r"(?:^|\n)##\s*○[^\n]{2,80}")

def compact_with_indices(value):
    parts = []
    indices = []
    for offset, original in enumerate(value):
        expanded = unicodedata.normalize("NFKC", original)
        for char in expanded:
            if char.isalnum() or ('가' <= char <= '힣'):
                parts.append(char.casefold())
                indices.append(offset)
    return "".join(parts), indices

def compact(value):
    return compact_with_indices(value)[0]

def source_excerpt(text, mapping, start, length):
    a = mapping[start]
    b = mapping[min(start + length - 1, len(mapping) - 1)] + 1
    lo = max(0, a - 360)
    hi = min(len(text), b + 360)
    segment = text[lo:hi]
    return {
        "excerpt": segment,
        "title_at_excerpt_offset": a - lo,
        "names_near_title_unverified": sorted(set(NAME.findall(segment))),
        "speaker_headings": SPEAKER.findall(segment)[:10],
    }

def candidate_occurrences(body, title, window=5, normalized=None, mapping=None):
    """Locate normalized exact and conservative prefix mentions.

    Prefix evidence is weak, only for discovery when an exact title is absent.
    """
    if normalized is None or mapping is None:
        norm, mapping = compact_with_indices(body)
    else:
        norm = normalized
    wanted = compact(title)
    if len(wanted) < 12:
        return []
    hits = []
    start = 0
    while len(hits) < window:
        at = norm.find(wanted, start)
        if at < 0:
            break
        hits.append({"match": "exact_title", **source_excerpt(body, mapping, at, len(wanted))})
        start = at + len(wanted)
    if hits:
        return hits
    # Allow partial-title search to find a possible spelling/editorial mismatch.
    prefix = wanted[:min(22, max(14, int(len(wanted) * 0.65)))]
    start = 0
    while len(hits) < 3:
        at = norm.find(prefix, start)
        if at < 0:
            break
        hits.append({"match": "partial_prefix_only", **source_excerpt(body, mapping, at, len(prefix))})
        start = at + len(prefix)
    return hits

def near_day(date, proposal, processed):
    try:
        day = dt.date.fromisoformat(date)
        initial = dt.date.fromisoformat(proposal)
        # Later council sessions may revisit pending bills; do not silently
        # omit that evidence if title and session match.
        end = dt.date.fromisoformat(processed) if processed else initial + dt.timedelta(days=365)
        return initial - dt.timedelta(days=60) <= day <= end + dt.timedelta(days=45)
    except (TypeError, ValueError):
        return False

def session_match(session, meeting_title):
    m = re.search(r"(\d+)\s*회", str(session or ""))
    if not m:
        return False
    # Ignore the full term's range in the prefix, e.g. (제37회 ~ 제70회).
    title = meeting_title or ""
    if re.match(r"^제\s*\d+\s*대\s*의회\s*\(", title):
        title = title.split(")", 1)[-1]
    actual = re.search(r"제\s*0*(\d+)\s*회", title)
    return bool(actual and int(actual[1]) == int(m[1]))

def discover(root=ROOT):
    missing = json.loads((root/"reports/bill-data-audit.json").read_text(encoding="utf-8"))["member_bills_without_names"]
    meetings = json.loads((root/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
    if len(missing) != 25:
        raise ValueError(f"expected 25 unresolved bills in snapshot, found {len(missing)}")
    by_term = collections.defaultdict(list)
    for bill in missing:
        by_term[bill["term"]].append(bill)

    results = {}
    for bill in missing:
        if not bill.get("internal_number"):
            raise ValueError("unresolved bill without internal number")
        results[bill["internal_number"]] = {
            "internal_number": bill["internal_number"],
            "term": bill["term"],
            "bill_number": bill.get("bill_number"),
            "title": bill["title"],
            "session": bill.get("session"),
            "proposal_date": bill.get("proposal_date"),
            "processed_date": bill.get("processed_date"),
            "official_bill_url": bill.get("official_url"),
            "minutes_candidate_count": 0,
            "exact_title_meetings": 0,
            "same_session_meetings": 0,
            "candidate_minutes": [],
            "proposer_names_verified": [],
            "promotion_status": "not_promoted_source_review_required",
        }

    scanned = 0
    for meeting in meetings:
        candidates = [
            bill for bill in by_term.get(meeting["term"], ())
            if session_match(bill.get("session"), meeting.get("title"))
            or near_day(meeting.get("date"), bill.get("proposal_date"), bill.get("processed_date"))
        ]
        if not candidates:
            continue
        relative = meeting.get("path")
        if not relative or not (root / relative).is_file():
            raise ValueError(f"missing source minutes for {meeting.get('meeting_id')}")
        raw = (root / relative).read_text(encoding="utf-8")
        parts = raw.split("\n\n", 2)
        if len(parts) != 3:
            raise ValueError(f"malformed Markdown source for {meeting.get('meeting_id')}")
        body = parts[2]
        normalized, mapping = compact_with_indices(body)
        scanned += 1
        for bill in candidates:
            hits = candidate_occurrences(body, bill["title"], normalized=normalized, mapping=mapping)
            if not hits:
                continue
            entry = results[bill["internal_number"]]
            same_session = session_match(bill.get("session"), meeting.get("title"))
            date_near = near_day(meeting.get("date"), bill.get("proposal_date"), bill.get("processed_date"))
            excerpt_hits = hits[:3]
            entry["candidate_minutes"].append({
                "meeting_id": meeting["meeting_id"],
                "term": meeting["term"],
                "date": meeting["date"],
                "title": meeting.get("title"),
                "official_url": meeting.get("official_url"),
                "source_path": relative,
                "publication_status": meeting.get("publication_status"),
                "session_match": bool(same_session),
                "date_near_proposal_or_decision": bool(date_near),
                "matches": excerpt_hits,
            })
            if any(h["match"] == "exact_title" for h in hits):
                entry["exact_title_meetings"] += 1
            if same_session:
                entry["same_session_meetings"] += 1
    # Deterministic order and capped excerpts so reviewer can reproduce matches
    # without creating a large derived data file.
    for entry in results.values():
        entry["candidate_minutes"].sort(key=lambda x: (
            not x["session_match"],
            not x["date_near_proposal_or_decision"],
            not any(h["match"] == "exact_title" for h in x["matches"]),
            x["date"],
            x["meeting_id"],
        ))
        entry["minutes_candidate_count"] = len(entry["candidate_minutes"])
        entry["candidate_minutes"] = entry["candidate_minutes"][:20]
        entry["proposer_names_verified"] = []  # Do not auto-infer identity.
        entry["review_result"] = (
            "review_source_excerpt_required"
            if entry["minutes_candidate_count"] else "no_matching_minutes_title_found"
        )
    data = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "stored official-source Markdown only; no live source query",
        "proposer_names_promoted": 0,
        "source_rows_scanned": scanned,
        "missing_bill_count": len(missing),
        "bills_with_candidates": sum(x["minutes_candidate_count"] > 0 for x in results.values()),
        "bills_without_candidates": sum(x["minutes_candidate_count"] == 0 for x in results.values()),
        "bills": list(results.values()),
        "disclaimer": (
            "Title matching proves only meeting-text mention. Speaker and name "
            "mentions in snippets do not prove proposer role or full co-proposer roster."
        ),
    }
    return data

def main():
    result = discover(ROOT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_rows_scanned": result["source_rows_scanned"],
        "missing_bill_count": result["missing_bill_count"],
        "bills_with_candidates": result["bills_with_candidates"],
        "bills_without_candidates": result["bills_without_candidates"],
        "proposer_names_promoted": result["proposer_names_promoted"],
        "per_bill": [{
            "id": b["internal_number"],
            "term": b["term"],
            "candidates": b["minutes_candidate_count"],
            "exact": b["exact_title_meetings"],
            "same_session": b["same_session_meetings"],
        } for b in result["bills"]],
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
