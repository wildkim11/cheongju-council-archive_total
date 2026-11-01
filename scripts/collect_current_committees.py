"""Collect current official committee rosters.

Roster membership is resolved against the current official member list by exact name.
Displayed committee-period text is preserved, but a period that does not overlap the
current council term is flagged and is not silently applied to the current roster.
"""
from __future__ import annotations

import datetime as dt
import html as html_lib
import json
import re
import urllib.parse
from pathlib import Path

from archive_common import save_json
from collect_current_members import BASE, LIST_URL, fetch_text, parse_member_index, stable_person_id

ROOT=Path(__file__).resolve().parents[1]
COUNCIL_SCOPE="cheongju_integrated"
CURRENT_TERM=4
CURRENT_TERM_START=dt.date(2026,7,1)
SEED_URL=f"{BASE}/content/committee/coIntroduce_C306.html"


def _abs(url:str)->str:
    return urllib.parse.urljoin(BASE+"/",url)


def _visible_text(raw:str)->str:
    raw=re.sub(r"<br\s*/?>"," ",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",html_lib.unescape(raw)).strip()


def discover_committees(html:str)->list[dict]:
    found={}
    for m in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']*coIntroduce_([A-Za-z0-9]+)\.html[^"\']*)["\'][^>]*>([\s\S]*?)</a>',
        html,
        flags=re.I,
    ):
        href,code,label_raw=m.group(1),m.group(2),m.group(3)
        label=_visible_text(label_raw)
        if not label or "위원회" not in label:
            continue
        found[code]={
            "committee_code":code,
            "committee_name":label,
            "official_url":_abs(href),
        }
    if not found:
        raise ValueError("No official committee intro links discovered")
    return sorted(found.values(),key=lambda r:r["committee_name"])


def committee_type(name:str)->str:
    if "특별위원회" in name:
        return "special_committee"
    if "인사청문" in name:
        return "other_committee"
    return "standing_committee"


def _displayed_period(text:str)->dict:
    m=re.search(
        r"위원회\s*임기\s*:\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?"
        r"\s*~\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?",
        text,
    )
    if not m:
        return {"text":None,"start_date":None,"end_date":None}
    vals=list(map(int,m.groups()))
    start=dt.date(vals[0],vals[1],vals[2])
    end=dt.date(vals[3],vals[4],vals[5])
    return {
        "text":m.group(0),
        "start_date":start.isoformat(),
        "end_date":end.isoformat(),
    }


def parse_committee_page(html:str,expected_name:str)->dict:
    text=_visible_text(html)
    roles=[]
    seen=set()
    for m in re.finditer(r"([가-힣]{2,5})\s*(위원장|부위원장|위원)",text):
        name,role=m.group(1),m.group(2)
        # Avoid headings such as "위원장" without a person name; Korean-name regex handles this.
        key=(name,role)
        if key in seen:
            continue
        seen.add(key)
        roles.append({"name":name,"role":role})

    if not roles:
        raise ValueError(f"No committee roster parsed: {expected_name}")

    period=_displayed_period(text)
    period_conflict=False
    if period["end_date"]:
        period_conflict=dt.date.fromisoformat(period["end_date"]) < CURRENT_TERM_START

    return {
        "roles":roles,
        "displayed_period":period,
        "period_conflict_with_current_term":period_conflict,
    }


def collect(root:Path=ROOT)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    current_html=fetch_text(LIST_URL)
    members=parse_member_index(current_html)
    by_name={}
    for row in members:
        if row["name"] in by_name:
            raise ValueError(f"Duplicate current member name needs review: {row['name']}")
        by_name[row["name"]]=row

    seed_html=fetch_text(SEED_URL)
    committees=discover_committees(seed_html)

    committee_rows=[]
    membership_rows=[]
    unresolved=[]
    period_conflicts=[]

    for committee in committees:
        parsed=parse_committee_page(fetch_text(committee["official_url"]),committee["committee_name"])
        ctype=committee_type(committee["committee_name"])
        period=parsed["displayed_period"]
        apply_period=not parsed["period_conflict_with_current_term"]

        committee_rows.append({
            **committee,
            "committee_type":ctype,
            "council_scope":COUNCIL_SCOPE,
            "term":CURRENT_TERM,
            "displayed_period_text":period["text"],
            "displayed_start_date":period["start_date"],
            "displayed_end_date":period["end_date"],
            "period_conflict_with_current_term":parsed["period_conflict_with_current_term"],
            "checked_at":stamp,
        })
        if parsed["period_conflict_with_current_term"]:
            period_conflicts.append(committee["committee_code"])

        for item in parsed["roles"]:
            member=by_name.get(item["name"])
            if not member:
                unresolved.append({
                    "committee_code":committee["committee_code"],
                    "committee_name":committee["committee_name"],
                    **item,
                })
                continue
            membership_rows.append({
                "person_id":stable_person_id(member["f_code"]),
                "official_profile_code":member["f_code"],
                "council_scope":COUNCIL_SCOPE,
                "term":CURRENT_TERM,
                "membership_type":ctype,
                "committee_code":committee["committee_code"],
                "label":committee["committee_name"],
                "role":item["role"],
                "start_date":period["start_date"] if apply_period else None,
                "end_date":period["end_date"] if apply_period else None,
                "period_precision":"exact_date" if apply_period and period["start_date"] else "unknown",
                "source_url":committee["official_url"],
                "checked_at":stamp,
                "displayed_period_conflict":parsed["period_conflict_with_current_term"],
            })

    if unresolved:
        raise ValueError("Unresolved current committee members: "+json.dumps(unresolved,ensure_ascii=False))

    save_json(root/"archive/committees/current_committees.json",committee_rows)
    save_json(root/"archive/committees/current_memberships.json",membership_rows)
    report={
        "checked_at":stamp,
        "committee_count":len(committee_rows),
        "membership_rows":len(membership_rows),
        "by_type":{
            kind:sum(r["committee_type"]==kind for r in committee_rows)
            for kind in sorted({r["committee_type"] for r in committee_rows})
        },
        "period_conflict_codes":period_conflicts,
        "unresolved_members":0,
    }
    save_json(root/"reports/current-committees.json",report)
    return report


def main():
    print(json.dumps(collect(),ensure_ascii=False))


if __name__=="__main__":
    main()
