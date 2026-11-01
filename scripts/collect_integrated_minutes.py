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


def write_record(root: Path, row: dict, body: str, now: str) -> dict:
    content_hash = sha256_bytes(canonical(body).encode("utf-8"))
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
        "first_seen_at": now,
        "last_checked_at": now,
        "supersedes": None,
        "superseded_by": None,
    }


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


def run_full(root: Path = ROOT) -> dict:
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    today = now.date().isoformat()
    stamp = now.isoformat()
    rows, inventory_qa = read_official_inventory(today)
    rows.sort(key=lambda r: (r["date"], r["meeting_id"]))

    def download(row):
        return row, extract_minutes_body(fetch(row["official_url"]))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        downloaded = list(pool.map(download, rows))

    # All network reads must succeed before archive mutation.
    with tempfile.TemporaryDirectory(prefix="archive-integrated-") as tmp:
        stage = Path(tmp)
        output_rows = [write_record(stage, row, body, stamp) for row, body in downloaded]
        for src in stage.rglob("*"):
            if src.is_file():
                dst = root / src.relative_to(stage)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)

    save_json(root / "indexes/integrated/meetings.json", output_rows)
    report = {
        "checked_at": stamp,
        "council_scope": COUNCIL_SCOPE,
        "collected": len(output_rows),
        "published": sum(
            r["publication_status"] == "published" for r in output_rows
        ),
        "by_term": dict(collections.Counter(str(r["term"]) for r in output_rows)),
        "provisional": sum(
            r["publication_status"] == "provisional" for r in output_rows
        ),
        "inventory_qa": inventory_qa,
    }
    save_json(root / "reports/integrated-full.json", report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["inventory", "full"], default="inventory")
    args = parser.parse_args()
    result = run_inventory_only() if args.mode == "inventory" else run_full()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
