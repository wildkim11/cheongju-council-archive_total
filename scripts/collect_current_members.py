"""Collect current member source facts and one official portrait per member.

Historical rosters are handled by separate adapters because current affiliations
must never be backfilled into prior terms.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import html as html_lib
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
PROFILE_TEMPLATE = BASE + "/memberHome/content/profile.html?f_code={f_code}"
BILL_TEMPLATE = BASE + "/memberHome/content/bill.html?f_code={f_code}"
COUNCIL_SCOPE = "cheongju_integrated"
CURRENT_TERM = 4

TLS = ssl.create_default_context()
TLS.minimum_version = ssl.TLSVersion.TLSv1_2
CONNECTIONS = threading.local()


def _request(url: str) -> tuple[bytes, str]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "council.cheongju.go.kr":
        raise ValueError("Unexpected source host")

    target = parsed.path + ("?" + parsed.query if parsed.query else "")
    last = None
    for attempt in range(6):
        try:
            # Pace repeated official-site requests and reuse one connection.
            # The source server intermittently resets rapid TLS handshakes.
            time.sleep(0.25)
            connection = getattr(CONNECTIONS, "connection", None)
            if connection is None:
                connection = http.client.HTTPSConnection(
                    parsed.netloc, timeout=45, context=TLS
                )
                CONNECTIONS.connection = connection
            connection.request(
                "GET",
                target,
                headers={
                    "User-Agent": "CheongjuCouncilArchive/0.1",
                    "Accept": "*/*",
                    "Connection": "keep-alive",
                },
            )
            response = connection.getresponse()
            data = response.read()
            if response.status != 200:
                raise ValueError(f"Official source HTTP {response.status}")
            content_type = (response.getheader("Content-Type") or "").split(";", 1)[0].strip()
            return data, content_type
        except Exception as exc:
            last = exc
            connection = getattr(CONNECTIONS, "connection", None)
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            CONNECTIONS.connection = None
            if attempt == 5:
                raise
            time.sleep(min(8, 2 ** attempt))
    raise last


def fetch_text(url: str) -> str:
    data, _ = _request(url)
    return data.decode("utf-8-sig")


def _absolute(url: str) -> str:
    return urllib.parse.urljoin(BASE + "/", url)


def _visible_text(raw: str) -> str:
    raw = re.sub(r"<br\s*/?>", " ", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html_lib.unescape(raw)).strip()


def _member_section(html: str) -> str:
    m = re.search(
        r'<section\b[^>]*class=["\'][^"\']*\bmember\b[^"\']*["\'][^>]*>([\s\S]*?)</section>',
        html,
        flags=re.I,
    )
    if not m:
        raise ValueError("Missing current member section")
    return m.group(1)


def _query_code(href: str, key: str) -> str | None:
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(_absolute(href)).query)
    values = query.get(key)
    return values[0] if values else None


def _dd_value(raw: str, label: str) -> str | None:
    for dd in re.findall(r"<dd\b[^>]*>([\s\S]*?)</dd>", raw, flags=re.I):
        text = _visible_text(dd)
        m = re.match(rf"{re.escape(label)}\s*:\s*(.*)$", text)
        if m:
            value = re.sub(r"\s+", " ", m.group(1)).strip()
            return value or None
    return None


def parse_member_index(html: str) -> list[dict]:
    """Parse the official current-member list from the main content only."""
    section = _member_section(html)
    out = []
    seen = set()

    for raw in re.findall(r"<li\b[^>]*>([\s\S]*?)</li>", section, flags=re.I):
        if "<dl" not in raw.lower() or "f_code=" not in raw:
            continue

        f_href = re.search(
            r'href=["\']([^"\']*[?&]f_code=[^"\']+)["\']',
            raw,
            flags=re.I,
        )
        if not f_href:
            continue
        f_code = _query_code(f_href.group(1), "f_code")
        if not f_code or f_code in seen:
            continue

        m_href = re.search(
            r'href=["\']([^"\']*memberProfile\.html[^"\']*[?&]mcode=[^"\']+)["\']',
            raw,
            flags=re.I,
        )
        m_code = _query_code(m_href.group(1), "mcode") if m_href else None

        name_match = re.search(
            r'<dd\b[^>]*class=["\'][^"\']*\bname\b[^"\']*["\'][^>]*>([\s\S]*?)</dd>',
            raw,
            flags=re.I,
        )
        name = _visible_text(name_match.group(1)) if name_match else None

        image = re.search(
            r'<img\b[^>]*src=["\']([^"\']+)["\'][^>]*>',
            raw,
            flags=re.I,
        )
        portrait = _absolute(image.group(1)) if image else None
        if not name and image:
            alt = re.search(r'alt=["\']([^"\']+)["\']', image.group(0), flags=re.I)
            if alt:
                name = re.sub(r"\s*의원\s*$", "", html_lib.unescape(alt.group(1))).strip()

        if not name or not re.fullmatch(r"[가-힣]{2,5}", name):
            raise ValueError(f"Cannot resolve current member name for f_code={f_code}")

        committees_raw = _dd_value(raw, "소속위원회")
        committees = [
            x.strip()
            for x in (committees_raw or "").split(",")
            if x.strip()
        ]

        seen.add(f_code)
        out.append(
            {
                "f_code": f_code,
                "m_code": m_code,
                "name": name,
                "profile_url": PROFILE_TEMPLATE.format(f_code=f_code),
                "portrait_source_url": portrait,
                "district": _dd_value(raw, "선거구"),
                "party": _dd_value(raw, "소속정당"),
                "committees": committees,
                "source_url": LIST_URL,
            }
        )

    if not out:
        raise ValueError("No current members parsed from official member section")
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


def _career_items(html: str) -> list[str]:
    """Extract visible career list items from the official profile section."""
    section = re.search(
        r"경력사항([\s\S]*?)(?:홈\s*>|의정활동|발의의안|발언회의록|청주시의회\s+Cheongju City Council|</main>|</article>)",
        html,
        flags=re.I,
    )
    target = section.group(1) if section else html
    items = []
    for raw in re.findall(r"<li[^>]*>([\s\S]*?)</li>", target, flags=re.I):
        value = html_text(raw)
        value = re.sub(r"\s+", " ", value).strip()
        if value and value not in items:
            items.append(value)
    return items


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
        "career": _career_items(html),
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

        if row["portrait_source_url"]:
            if save_portraits:
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
            else:
                portrait = {
                    "source_url": row["portrait_source_url"],
                    "local_path": None,
                    "checked_at": stamp,
                    "sha256": None,
                }

        people.append(
            {
                "person_id": person_id,
                "name": row["name"],
                "aliases": [],
                "official_profile_url": row["profile_url"],
                "official_profile_code": row["f_code"],
                "official_roster_code": row.get("m_code"),
                "portrait": portrait,
                "career": profile["career"],
                "official_phone": profile.get("phone"),
                "official_email": profile.get("email"),
                "bill_url": BILL_TEMPLATE.format(f_code=row["f_code"]),
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
        if row.get("party"):
            parties.append(
                {
                    "person_id": person_id,
                    "council_scope": COUNCIL_SCOPE,
                    "term": CURRENT_TERM,
                    "party": row["party"],
                    "start_date": None,
                    "end_date": None,
                    "source_url": row["profile_url"],
                    "checked_at": stamp,
                }
            )
        if row.get("district"):
            districts.append(
                {
                    "person_id": person_id,
                    "council_scope": COUNCIL_SCOPE,
                    "term": CURRENT_TERM,
                    "district": row["district"],
                    "start_date": None,
                    "end_date": None,
                    "source_url": row["profile_url"],
                    "checked_at": stamp,
                }
            )
        for committee in row.get("committees", []):
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
        "portraits": sum(bool(p["portrait"]) and bool(p["portrait"].get("local_path")) for p in people),
        "portrait_sources": sum(bool(p["portrait"]) for p in people),
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
