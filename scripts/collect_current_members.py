"""Collect current member source facts and one official portrait per member.

Historical rosters are handled by separate adapters because current affiliations
must never be backfilled into prior terms.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import ssl
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from archive_common import save_json, save_text, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://council.cheongju.go.kr"
LIST_URL = BASE + "/content/member/member.html"
PROFILE_TEMPLATE = BASE + "/memberHome/content/bill.html?f_code={f_code}"
COUNCIL_SCOPE = "cheongju_integrated"
CURRENT_TERM = 4

TLS = ssl.create_default_context()
TLS.minimum_version = ssl.TLSVersion.TLSv1_2


def _request(url: str) -> tuple[bytes, str]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "council.cheongju.go.kr":
        raise ValueError("Unexpected source host")
    req = urllib.request.Request(url, headers={"User-Agent": "CheongjuCouncilArchive/0.1"})
    with urllib.request.urlopen(req, timeout=40, context=TLS) as resp:
        if resp.status != 200:
            raise ValueError(f"Official source HTTP {resp.status}")
        return resp.read(), resp.headers.get_content_type()


def fetch_text(url: str) -> str:
    data, _ = _request(url)
    return data.decode("utf-8-sig")


class BlockParser(HTMLParser):
    """Capture list-like HTML blocks containing official member-home links."""

    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.current = None
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li" and self.current is None:
            self.current = {"text": [], "links": [], "images": [], "depth": self.depth}
        if tag not in self.VOID_TAGS:
            self.depth += 1
        if self.current is not None:
            if tag == "a" and attrs.get("href"):
                self.current["links"].append(attrs["href"])
            if tag == "img" and attrs.get("src"):
                self.current["images"].append(
                    {"src": attrs["src"], "alt": attrs.get("alt", "")}
                )

    def handle_endtag(self, tag):
        self.depth = max(0, self.depth - 1)
        if tag == "li" and self.current is not None and self.depth == self.current["depth"]:
            if any("f_code=" in link for link in self.current["links"]):
                self.blocks.append(self.current)
            self.current = None

    def handle_data(self, data):
        if self.current is not None and data.strip():
            self.current["text"].append(data.strip())


def _absolute(url: str) -> str:
    return urllib.parse.urljoin(BASE + "/", url)


def _f_code(links: list[str]) -> str | None:
    for link in links:
        m = re.search(r"[?&]f_code=([A-Za-z0-9_-]+)", link)
        if m:
            return m.group(1)
    return None


def _name(block: dict) -> str:
    for image in block["images"]:
        m = re.fullmatch(r"\s*([가-힣]{2,5})\s*의원\s*", image.get("alt", ""))
        if m:
            return m.group(1)
    text = " ".join(block["text"])
    for token in re.findall(r"[가-힣]{2,5}", text):
        if token not in {"선거구", "소속정당", "소속위원회", "상세프로필", "누리집"}:
            return token
    raise ValueError("Cannot resolve member name")


def parse_member_index(html: str) -> list[dict]:
    parser = BlockParser()
    parser.feed(html)
    out = []
    seen = set()
    for block in parser.blocks:
        f_code = _f_code(block["links"])
        if not f_code or f_code in seen:
            continue
        seen.add(f_code)
        portrait = None
        for image in block["images"]:
            if "의원" in image.get("alt", ""):
                portrait = _absolute(image["src"])
                break
        out.append(
            {
                "f_code": f_code,
                "name": _name(block),
                "profile_url": PROFILE_TEMPLATE.format(f_code=f_code),
                "portrait_source_url": portrait,
            }
        )
    return out


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("li", "p", "div", "br", "dt", "dd"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if tag in ("li", "p", "div", "dt", "dd"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(html: str) -> str:
    p = PlainText()
    p.feed(html)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", "".join(p.parts))).strip()


def _field(text: str, label: str, next_labels: list[str]) -> str | None:
    stop = "|".join(re.escape(x) for x in next_labels)
    m = re.search(
        rf"{re.escape(label)}\s*:\s*(.+?)(?=\s*(?:{stop})\s*:|\n|$)",
        text,
        flags=re.S,
    )
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def parse_profile(html: str) -> dict:
    text = html_text(html)
    labels = ["선거구", "소속정당", "소속위원회", "전화번호", "이메일"]
    return {
        "district": _field(text, "선거구", labels[1:]),
        "party": _field(text, "소속정당", labels[2:]),
        "committees": [
            x.strip()
            for x in (_field(text, "소속위원회", labels[3:]) or "").split(",")
            if x.strip()
        ],
        "phone": _field(text, "전화번호", labels[4:]),
        "email": _field(text, "이메일", []),
    }


def stable_person_id(f_code: str) -> str:
    return "person-fcode-" + re.sub(r"[^A-Za-z0-9_-]", "_", f_code)


def _portrait_extension(content_type: str, url: str) -> str:
    mapping = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if content_type in mapping:
        return mapping[content_type]
    suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".img"


def run(root: Path = ROOT, save_portraits: bool = True) -> dict:
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    index_html = fetch_text(LIST_URL)
    index_rows = parse_member_index(index_html)
    if not index_rows:
        raise ValueError("No current member profiles found")

    people = []
    tenures = []
    parties = []
    districts = []
    committees = []

    for row in index_rows:
        person_id = stable_person_id(row["f_code"])
        profile = parse_profile(fetch_text(row["profile_url"]))
        portrait = None

        if save_portraits and row["portrait_source_url"]:
            data, content_type = _request(row["portrait_source_url"])
            ext = _portrait_extension(content_type, row["portrait_source_url"])
            local_path = f"archive/people/portraits/{person_id}{ext}"
            path = root / local_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            portrait = {
                "source_url": row["portrait_source_url"],
                "local_path": local_path,
                "checked_at": stamp,
                "sha256": sha256_bytes(data),
            }

        people.append(
            {
                "person_id": person_id,
                "name": row["name"],
                "aliases": [],
                "official_profile_url": row["profile_url"],
                "official_profile_code": row["f_code"],
                "portrait": portrait,
                "source_url": LIST_URL,
                "checked_at": stamp,
            }
        )
        tenures.append(
            {
                "person_id": person_id,
                "council_scope": COUNCIL_SCOPE,
                "term": CURRENT_TERM,
                "start_date": None,
                "end_date": None,
                "source_url": row["profile_url"],
                "checked_at": stamp,
            }
        )
        if profile["party"]:
            parties.append(
                {
                    "person_id": person_id,
                    "council_scope": COUNCIL_SCOPE,
                    "term": CURRENT_TERM,
                    "party": profile["party"],
                    "start_date": None,
                    "end_date": None,
                    "source_url": row["profile_url"],
                    "checked_at": stamp,
                }
            )
        if profile["district"]:
            districts.append(
                {
                    "person_id": person_id,
                    "council_scope": COUNCIL_SCOPE,
                    "term": CURRENT_TERM,
                    "district": profile["district"],
                    "start_date": None,
                    "end_date": None,
                    "source_url": row["profile_url"],
                    "checked_at": stamp,
                }
            )
        for committee in profile["committees"]:
            committees.append(
                {
                    "person_id": person_id,
                    "council_scope": COUNCIL_SCOPE,
                    "term": CURRENT_TERM,
                    "committee": committee,
                    "role": None,
                    "start_date": None,
                    "end_date": None,
                    "source_url": row["profile_url"],
                    "checked_at": stamp,
                }
            )

    save_json(root / "archive/people/people.json", people)
    save_json(root / "archive/people/tenures.json", tenures)
    save_json(root / "archive/people/party_memberships.json", parties)
    save_json(root / "archive/people/district_memberships.json", districts)
    save_json(root / "archive/people/committee_memberships.json", committees)
    report = {
        "checked_at": stamp,
        "current_members": len(people),
        "portraits": sum(bool(p["portrait"]) for p in people),
        "party_rows": len(parties),
        "district_rows": len(districts),
        "committee_rows": len(committees),
    }
    save_json(root / "reports/current-members.json", report)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-portraits", action="store_true")
    args = p.parse_args()
    print(json.dumps(run(save_portraits=not args.no_portraits), ensure_ascii=False))


if __name__ == "__main__":
    main()
