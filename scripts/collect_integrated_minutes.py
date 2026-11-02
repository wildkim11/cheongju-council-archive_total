"""Collect integrated Cheongju City Council public minutes for terms 1-4.

This module intentionally stores source facts only. It does not create analytical
labels, rankings, policy classifications, EVENT clusters, or Q/P codes.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import datetime as dt
import http.client
import json
import re
import shutil
import ssl
import tempfile
import threading
import time
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

from archive_common import save_json, save_text, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://councilrec.cheongju.go.kr"
COUNCIL_SCOPE = "cheongju_integrated"
SUPPORTED_TERMS = (1, 2, 3, 4)

TLS = ssl.create_default_context()
TLS.minimum_version = ssl.TLSVersion.TLSv1_2
TLS.set_ciphers("DEFAULT")
CONNECTIONS = threading.local()


def fetch(url: str, params: dict | None = None) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "councilrec.cheongju.go.kr":
        raise ValueError("Unexpected source host")

    target = parsed.path + ("?" + parsed.query if parsed.query else "")
    for attempt in range(3):
        try:
            time.sleep(0.2)
            connection = getattr(CONNECTIONS, "connection", None)
            if connection is None:
                connection = http.client.HTTPSConnection(
                    parsed.netloc, timeout=40, context=TLS
                )
                CONNECTIONS.connection = connection

            body = None if params is None else urllib.parse.urlencode(params).encode()
            connection.request(
                "GET" if body is None else "POST",
                target,
                body,
                {
                    "User-Agent": "CheongjuCouncilArchive/0.1",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response = connection.getresponse()
            data = response.read()
            if response.status != 200:
                raise ValueError(f"Official source HTTP {response.status}")
            return data.decode("utf-8-sig")
        except Exception:
            connection = getattr(CONNECTIONS, "connection", None)
            if connection:
                connection.close()
            CONNECTIONS.connection = None
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def _endpoint(kind: str) -> str:
    if kind not in {"Year", "Gnrtn"}:
        raise ValueError(f"Unsupported inventory kind: {kind}")
    return BASE + f"/minutes/svc/web/cms/mnts/SvcMntsTree{kind}.php"


def _tree(kind: str, node: dict) -> list[dict]:
    payload = {k: v for k, v in node.items() if k.startswith("var")}
    rows = json.loads(fetch(_endpoint(kind), payload))
    if not isinstance(rows, list):
        raise ValueError("Invalid official inventory")
    return rows


def _meeting_type(title: str, committee_code: str | None) -> str:
    text = title or ""
    if "본회의" in text:
        return "plenary"
    if "예산결산특별위원회" in text:
        return "budget_special_committee"
    if "행정사무감사" in text:
        return "administrative_audit"
    if "행정사무조사" in text:
        return "administrative_investigation"
    if "특별위원회" in text:
        return "special_committee"
    if "위원회" in text or committee_code:
        return "committee"
    return "other"


def inventory_by_term(today: str) -> list[dict]:
    """Read the official generation tree and collect terms 1-4.

    The official term value is the source of truth. We do not infer the term
    from meeting dates.
    """

    roots = _tree("Gnrtn", {"var10": "SvcMntsTreeGnrtn"})
    selected = [
        node
        for node in roots
        if str(node.get("var01", "")).isdigit()
        and int(node["var01"]) in SUPPORTED_TERMS
    ]
    if len(selected) != len(SUPPORTED_TERMS):
        found = sorted(
            int(node["var01"])
            for node in selected
            if str(node.get("var01", "")).isdigit()
        )
        raise ValueError(f"Expected integrated terms 1-4; found {found}")

    out: list[dict] = []

    def branch(node: dict, term: int, parent_text: str = "", depth: int = 0):
        if depth > 8:
            raise ValueError("Unexpected tree depth")

        for child in _tree("Gnrtn", node):
            title = (parent_text + " " + str(child.get("text", ""))).strip()
            if child.get("var12"):
                m = re.search(r"(20\d{2})\.(\d{2})\.(\d{2})", title)
                if not m or not str(child["var12"]).isdigit():
                    raise ValueError("Invalid meeting metadata")
                date = dt.date(*map(int, m.groups())).isoformat()
                if date > today:
                    continue
                status = child.get("var09")
                if status not in ("Y", "N"):
                    raise ValueError("Unknown publication status")
                committee_code = child.get("var02")
                source_id = str(child["var12"])
                out.append(
                    {
                        "meeting_id": f"{COUNCIL_SCOPE}:minutes-{source_id}",
                        "legacy_minutes_id": f"minutes-{source_id}",
                        "council_scope": COUNCIL_SCOPE,
                        "term": term,
                        "title": title,
                        "date": date,
                        "year": int(date[:4]),
                        "committee_code": committee_code,
                        "meeting_type": _meeting_type(title, committee_code),
                        "publication_status": (
                            "provisional" if status == "N" else "published"
                        ),
                        "official_url": (
                            BASE
                            + "/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="
                            + source_id
                        ),
                        "source_id": source_id,
                    }
                )
            else:
                branch(child, term, title, depth + 1)

    for root in selected:
        term = int(root["var01"])
        branch(root, term, str(root.get("text", "")))

    if not out:
        raise ValueError("Empty official term inventory")
    return out


def inventory_by_year(today: str) -> list[dict]:
    """Read the official year tree for coverage cross-checking.

    Year inventory rows intentionally do not receive a term here. Term assignment
    comes only from the official generation/term inventory.
    """
    roots = _tree("Year", {"var10": "SvcMntsTreeYearGnrtn"})
    current_year = int(today[:4])
    selected = [
        node for node in roots
        if str(node.get("var01", "")).isdigit()
        and 2014 <= int(node["var01"]) <= current_year
    ]
    if not selected:
        raise ValueError("Empty official year roots")

    out: list[dict] = []

    def branch(node: dict, parent_text: str = "", depth: int = 0):
        if depth > 8:
            raise ValueError("Unexpected year-tree depth")
        for child in _tree("Year", node):
            title = (parent_text + " " + str(child.get("text", ""))).strip()
            if child.get("var12"):
                m = re.search(r"(20\d{2})\.(\d{2})\.(\d{2})", title)
                if not m or not str(child["var12"]).isdigit():
                    raise ValueError("Invalid year-inventory meeting metadata")
                date = dt.date(*map(int, m.groups())).isoformat()
                if date > today:
                    continue
                status = child.get("var09")
                if status not in ("Y", "N"):
                    raise ValueError("Unknown publication status")
                committee_code = child.get("var02")
                source_id = str(child["var12"])
                out.append(
                    {
                        "source_id": source_id,
                        "title": title,
                        "date": date,
                        "year": int(date[:4]),
                        "committee_code": committee_code,
                        "meeting_type": _meeting_type(title, committee_code),
                        "publication_status": (
                            "provisional" if status == "N" else "published"
                        ),
                        "official_url": (
                            BASE
                            + "/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="
                            + source_id
                        ),
                    }
                )
            else:
                branch(child, title, depth + 1)

    for root in selected:
        branch(root, str(root.get("text", "")))

    if not out:
        raise ValueError("Empty official year inventory")
    return out


def merge_official_inventories(term_rows: list[dict], year_rows: list[dict]) -> tuple[list[dict], dict]:
    """Cross-check both official inventories while keeping term inventory authoritative."""
    term_map = {row["source_id"]: row for row in term_rows}
    year_map = {row["source_id"]: row for row in year_rows}
    if len(term_map) != len(term_rows):
        raise ValueError("Duplicate source_id in official term inventory")
    if len(year_map) != len(year_rows):
        raise ValueError("Duplicate source_id in official year inventory")

    shared = set(term_map) & set(year_map)
    for source_id in shared:
        a, b = term_map[source_id], year_map[source_id]
        for key in ("date", "committee_code", "publication_status"):
            if a.get(key) != b.get(key):
                raise ValueError(
                    f"Conflicting official inventories for {source_id}: {key}"
                )

    only_term = sorted(set(term_map) - set(year_map))
    only_year = sorted(set(year_map) - set(term_map))

    # A year-only row has no source-supported term assignment. Do not infer it.
    if only_year:
        raise ValueError(
            "Year inventory contains rows absent from term inventory; "
            "manual review required: " + ",".join(only_year[:50])
        )

    merged = []
    for source_id, row in term_map.items():
        merged.append(
            {
                **row,
                "inventory_sources": (
                    ["term", "year"] if source_id in year_map else ["term"]
                ),
            }
        )
    qa = {
        "term_inventory_count": len(term_rows),
        "year_inventory_count": len(year_rows),
        "shared_count": len(shared),
        "only_term": only_term,
        "only_year": only_year,
    }
    return merged, qa


def read_official_inventory(today: str) -> tuple[list[dict], dict]:
    """Read both official trees concurrently and return cross-checked rows."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        term_future = pool.submit(inventory_by_term, today)
        year_future = pool.submit(inventory_by_year, today)
        term_rows = term_future.result()
        year_rows = year_future.result()
    return merge_official_inventories(term_rows, year_rows)


class Plain(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "br", "tr", "div"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in ("p", "div"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def extract_minutes_body(raw: str) -> str:
    match = re.search(
        r"<!-- 회의록내용 -->([\s\S]*?)(?:<!--// 회의록내용|<!-- //회의록내용|<div class=\"pageTopBtn\")",
        raw,
    )
    if match:
        section = match[1]
    else:
        start = raw.find("<div id='anh'>")
        end = raw.find("<!--// minutesContent", start)
        if start < 0 or end < start:
            raise ValueError("Missing official minutes body")
        section = raw[start:end]

    parser = Plain()
    parser.feed(section)
    text = re.sub(r"\n\s*\n+", "\n\n", "".join(parser.parts)).strip()
    if len(text) < 100 and "개의되지 않음" not in text:
        raise ValueError("Empty or unexpected minutes body")
    return text


def canonical(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _record_path(row: dict) -> str:
    return (
        f"archive/meetings/{row['council_scope']}/term-{row['term']}/"
        f"{row['year']}/{row['legacy_minutes_id']}.md"
    )


def _meeting_key(row: dict) -> tuple:
    title = (row.get("title") or "").split("(")[0]
    title = re.sub(r"\s+", " ", title).strip()
    return (row.get("committee_code"), title)


def detect_replacements(old_rows: list[dict], live_rows: list[dict]) -> dict[str, str]:
    """Map disappeared provisional meeting IDs to replacement official IDs.

    Never infer replacements for published records. Ambiguous or unexplained
    disappearance is a hard QA failure.
    """
    old = {row["meeting_id"]: row for row in old_rows}
    live = {row["meeting_id"]: row for row in live_rows}
    missing = sorted(set(old) - set(live))
    new_rows = [row for row in live_rows if row["meeting_id"] not in old]
    replacements: dict[str, str] = {}

    for old_id in missing:
        row = old[old_id]
        if row.get("publication_status") != "provisional":
            raise ValueError(
                f"Published meeting disappeared from official inventory: {old_id}"
            )
        if not row.get("date"):
            raise ValueError(f"Provisional meeting missing date: {old_id}")

        d0 = dt.date.fromisoformat(row["date"])
        matches = []
        for candidate in new_rows:
            if _meeting_key(candidate) != _meeting_key(row):
                continue
            d1 = dt.date.fromisoformat(candidate["date"])
            if (
                abs((d1 - d0).days) <= 3
                and candidate.get("publication_status") == "published"
            ):
                matches.append(candidate["meeting_id"])

        if len(matches) != 1:
            raise ValueError(
                f"Provisional disappearance needs manual review: {old_id}; "
                f"replacement candidates={matches}"
            )
        replacements[old_id] = matches[0]

    # Each disappeared provisional source must map to a DIFFERENT published
    # successor. A many-to-one match can silently relabel two old originals as
    # superseded by one new record and falsify the provenance graph.
    successor_ids=list(replacements.values())
    if len(successor_ids) != len(set(successor_ids)):
        raise ValueError(
            "Ambiguous many-to-one provisional replacements need manual review: "
            + repr(replacements)
        )
    return replacements


def write_record(
    root: Path,
    row: dict,
    body: str | None,
    now: str,
    old: dict | None = None,
    supersedes: str | None = None,
) -> dict:
    if body is None:
        if old is None:
            raise ValueError(f"Missing body for new meeting: {row['meeting_id']}")
        return {
            **old,
            **row,
            "last_checked_at": now,
            "supersedes": supersedes or old.get("supersedes"),
        }

    content_hash = sha256_bytes(canonical(body).encode("utf-8"))
    if old and old.get("content_sha256") == content_hash:
        return {
            **old,
            **row,
            "last_checked_at": now,
            "supersedes": supersedes or old.get("supersedes"),
        }

    source = (
        f"# {row['title']}\n\n"
        f"- official_url: {row['official_url']}\n"
        f"- meeting_date: {row['date']}\n"
        f"- collected_at: {now}\n"
        f"- source_id: {row['source_id']}\n"
        f"- council_scope: {row['council_scope']}\n"
        f"- term: {row['term']}\n"
        f"- publication_status: {row['publication_status']}\n\n"
        + re.sub(r"(?m)^○", "## ○", body)
        + "\n"
    )
    path = _record_path(row)
    save_text(root / path, source)
    payload = source.encode("utf-8")
    return {
        **row,
        "path": path,
        "content_sha256": content_hash,
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
        "first_seen_at": old.get("first_seen_at") if old else now,
        "last_checked_at": now,
        "supersedes": supersedes or (old.get("supersedes") if old else None),
        "superseded_by": None,
    }


def _load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"Expected list index: {path}")
    return value


def run_inventory_only(root: Path = ROOT) -> dict:
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    today = now.date().isoformat()
    rows, inventory_qa = read_official_inventory(today)
    rows.sort(key=lambda r: (r["date"], r["meeting_id"]))

    counts = collections.Counter(str(r["term"]) for r in rows)
    report = {
        "checked_at": now.isoformat(),
        "council_scope": COUNCIL_SCOPE,
        "listed": len(rows),
        "published": sum(r["publication_status"] == "published" for r in rows),
        "by_term": dict(counts),
        "provisional": sum(r["publication_status"] == "provisional" for r in rows),
        "inventory_qa": inventory_qa,
    }
    save_json(root / "indexes/integrated/meeting_inventory.json", rows)
    save_json(root / "reports/integrated-inventory.json", report)
    return report


def run_sync(mode: str, root: Path = ROOT) -> dict:
    if mode not in {"incremental", "full"}:
        raise ValueError("mode must be incremental or full")

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    today = now.date().isoformat()
    stamp = now.isoformat()

    live_rows, inventory_qa = read_official_inventory(today)
    live_rows.sort(key=lambda r: (r["date"], r["meeting_id"]))

    current_path = root / "indexes/integrated/meetings.json"
    history_path = root / "indexes/integrated/meeting_history.json"
    old_rows = _load_rows(current_path)
    old = {row["meeting_id"]: row for row in old_rows}
    history_rows = _load_rows(history_path)

    replacements = detect_replacements(old_rows, live_rows) if old_rows else {}
    reverse_replacements = {new: old_id for old_id, new in replacements.items()}

    needed = []
    for row in live_rows:
        prior = old.get(row["meeting_id"])
        if (
            mode == "full"
            or prior is None
            or prior.get("publication_status") != row["publication_status"]
            or row["publication_status"] == "provisional"
        ):
            needed.append(row)

    def download(row):
        try:
            return row["meeting_id"], extract_minutes_body(fetch(row["official_url"]))
        except Exception as error:
            raise RuntimeError(f"Failed meeting {row['meeting_id']}") from error

    bodies: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for meeting_id, body in pool.map(download, needed):
            bodies[meeting_id] = body

    with tempfile.TemporaryDirectory(prefix="archive-integrated-sync-") as tmp:
        stage = Path(tmp)
        # Copy current archive first so superseded provisional files are retained.
        for directory in ("archive", "indexes", "reports"):
            src = root / directory
            if src.exists():
                shutil.copytree(src, stage / directory)

        output_rows = []
        for row in live_rows:
            meeting_id = row["meeting_id"]
            output_rows.append(
                write_record(
                    stage,
                    row,
                    bodies.get(meeting_id),
                    stamp,
                    old=old.get(meeting_id),
                    supersedes=reverse_replacements.get(meeting_id),
                )
            )

        history_map = {row["meeting_id"]: row for row in history_rows}
        for old_id, new_id in replacements.items():
            previous = old[old_id]
            history_map[old_id] = {
                **previous,
                "publication_status": "superseded",
                "superseded_by": new_id,
                "last_checked_at": stamp,
            }

        history_out = sorted(
            history_map.values(), key=lambda r: (r.get("date", ""), r["meeting_id"])
        )
        save_json(stage / "indexes/integrated/meetings.json", output_rows)
        save_json(stage / "indexes/integrated/meeting_history.json", history_out)

        new_ids = sorted(set(r["meeting_id"] for r in live_rows) - set(old))
        changed_ids = sorted(
            row["meeting_id"]
            for row in output_rows
            if row["meeting_id"] in old
            and row.get("content_sha256") != old[row["meeting_id"]].get("content_sha256")
        )
        report = {
            "checked_at": stamp,
            "mode": mode,
            "council_scope": COUNCIL_SCOPE,
            "listed": len(output_rows),
            "published": sum(
                r["publication_status"] == "published" for r in output_rows
            ),
            "provisional": sum(
                r["publication_status"] == "provisional" for r in output_rows
            ),
            "by_term": dict(
                collections.Counter(str(r["term"]) for r in output_rows)
            ),
            "new": new_ids,
            "changed": changed_ids,
            "superseded": replacements,
            "bodies_checked": len(bodies),
            "history_rows": len(history_out),
            "inventory_qa": inventory_qa,
        }
        save_json(stage / "reports/integrated-sync.json", report)

        # Validate staged archive before replacing working files.
        import validate_archive
        validate_archive.validate(stage)

        for src in stage.rglob("*"):
            if src.is_file():
                dst = root / src.relative_to(stage)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)

    return report



def _initial_shard_path(root: Path, term: int) -> Path:
    return root / f"indexes/integrated/initial_term_{term}.json"


def _initial_shard_complete(root: Path, live_rows: list[dict], shard_rows: list[dict]) -> bool:
    if not shard_rows:
        return False
    live = {r["meeting_id"]: r for r in live_rows}
    shard = {r["meeting_id"]: r for r in shard_rows}
    if set(live) != set(shard):
        return False
    for meeting_id, row in live.items():
        prior = shard[meeting_id]
        for key in ("term", "date", "source_id", "publication_status", "official_url"):
            if prior.get(key) != row.get(key):
                return False
        path = prior.get("path")
        if not path or not (root / path).exists():
            return False
        if not prior.get("content_sha256"):
            return False
    return True


def run_initial_term(term: int, root: Path = ROOT) -> dict:
    """Populate one integrated-council term as a durable initial shard.

    Initial population is intentionally checkpointed by term. A retry skips a
    shard only when its exact live inventory and all archived body files still
    match. Canonical meetings.json is not published until assemble_initial().
    """
    if term not in SUPPORTED_TERMS:
        raise ValueError(f"Unsupported integrated term: {term}")

    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    today = now.date().isoformat()
    stamp = now.isoformat()
    all_rows, inventory_qa = read_official_inventory(today)
    live_rows = [r for r in all_rows if r["term"] == term]
    live_rows.sort(key=lambda r: (r["date"], r["meeting_id"]))
    if not live_rows:
        raise ValueError(f"Empty official inventory for term {term}")

    shard_path = _initial_shard_path(root, term)
    old_shard = _load_rows(shard_path)
    if _initial_shard_complete(root, live_rows, old_shard):
        report = {
            "checked_at": stamp,
            "mode": "initial-term",
            "term": term,
            "status": "already_complete",
            "listed": len(old_shard),
            "published": sum(r["publication_status"] == "published" for r in old_shard),
            "provisional": sum(r["publication_status"] == "provisional" for r in old_shard),
            "bodies_checked": 0,
            "inventory_qa": inventory_qa,
        }
        save_json(root / f"reports/integrated-initial-term-{term}.json", report)
        return report

    def download(row):
        try:
            return row, extract_minutes_body(fetch(row["official_url"]))
        except Exception as error:
            raise RuntimeError(f"Failed meeting {row['meeting_id']}") from error

    downloaded = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for row, body in pool.map(download, live_rows):
            downloaded.append((row, body))

    with tempfile.TemporaryDirectory(prefix=f"archive-integrated-term-{term}-") as tmp:
        stage = Path(tmp)
        output_rows = [
            write_record(stage, row, body, stamp)
            for row, body in downloaded
        ]
        output_rows.sort(key=lambda r: (r["date"], r["meeting_id"]))

        if len(output_rows) != len(live_rows):
            raise ValueError(f"Term {term} body count mismatch")
        for row in output_rows:
            path = row.get("path")
            if not path or not (stage / path).exists():
                raise ValueError(f"Term {term} staged body missing: {row['meeting_id']}")

        save_json(stage / f"indexes/integrated/initial_term_{term}.json", output_rows)
        report = {
            "checked_at": stamp,
            "mode": "initial-term",
            "term": term,
            "status": "populated",
            "listed": len(output_rows),
            "published": sum(r["publication_status"] == "published" for r in output_rows),
            "provisional": sum(r["publication_status"] == "provisional" for r in output_rows),
            "bodies_checked": len(downloaded),
            "inventory_qa": inventory_qa,
        }
        save_json(stage / f"reports/integrated-initial-term-{term}.json", report)

        for src in stage.rglob("*"):
            if src.is_file():
                dst = root / src.relative_to(stage)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)

    return report


def assemble_initial(root: Path = ROOT) -> dict:
    """Assemble term shards into the canonical current meeting index.

    The final assembly requires exact equality with a fresh official inventory.
    If the source changes while terms are being populated, assembly fails rather
    than silently mixing snapshots.
    """
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    today = now.date().isoformat()
    stamp = now.isoformat()
    live_rows, inventory_qa = read_official_inventory(today)
    live = {r["meeting_id"]: r for r in live_rows}

    merged = []
    by_term = {}
    for term in SUPPORTED_TERMS:
        rows = _load_rows(_initial_shard_path(root, term))
        if not rows:
            raise ValueError(f"Initial term shard missing: {term}")
        by_term[str(term)] = len(rows)
        merged.extend(rows)

    shard = {r["meeting_id"]: r for r in merged}
    if len(shard) != len(merged):
        raise ValueError("Duplicate meeting_id across initial term shards")
    if set(shard) != set(live):
        missing = sorted(set(live) - set(shard))
        extra = sorted(set(shard) - set(live))
        raise ValueError(
            "Initial shards do not match fresh official inventory; "
            f"missing={missing[:20]} extra={extra[:20]}"
        )

    canonical = []
    for meeting_id, live_row in live.items():
        row = shard[meeting_id]
        for key in ("term", "date", "source_id", "publication_status", "official_url"):
            if row.get(key) != live_row.get(key):
                raise ValueError(
                    f"Initial shard stale for {meeting_id}: {key} "
                    f"{row.get(key)!r} != {live_row.get(key)!r}"
                )
        path = row.get("path")
        if not path or not (root / path).exists():
            raise ValueError(f"Canonical meeting body missing: {meeting_id}")
        canonical.append({**row, **live_row})

    canonical.sort(key=lambda r: (r["date"], r["meeting_id"]))
    save_json(root / "indexes/integrated/meetings.json", canonical)
    history_path = root / "indexes/integrated/meeting_history.json"
    if not history_path.exists():
        save_json(history_path, [])

    report = {
        "checked_at": stamp,
        "mode": "assemble-initial",
        "listed": len(canonical),
        "published": sum(r["publication_status"] == "published" for r in canonical),
        "provisional": sum(r["publication_status"] == "provisional" for r in canonical),
        "by_term": by_term,
        "history_rows": len(_load_rows(history_path)),
        "inventory_qa": inventory_qa,
    }
    save_json(root / "reports/integrated-sync.json", report)

    import validate_archive
    validate_archive.validate(root)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["inventory", "incremental", "full", "initial-term", "assemble-initial"],
        default="inventory",
    )
    parser.add_argument("--term", type=int, choices=SUPPORTED_TERMS)
    args = parser.parse_args()
    if args.mode == "inventory":
        result = run_inventory_only()
    elif args.mode == "initial-term":
        if args.term is None:
            parser.error("--term is required with --mode initial-term")
        result = run_initial_term(args.term)
    elif args.mode == "assemble-initial":
        result = assemble_initial()
    else:
        result = run_sync(args.mode)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
