"""Collect current-year official council research-group rosters.

The official research-group overview table is the source of truth for group name,
member count, full participant list, and representative role.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html as html_lib
import json
import re
from pathlib import Path

from archive_common import save_json
from collect_current_members import (
    BASE, LIST_URL, fetch_text, parse_member_index, stable_person_id,
)

ROOT=Path(__file__).resolve().parents[1]
URL=f"{BASE}/content/activity/researchActivities.html"
COUNCIL_SCOPE="cheongju_integrated"
CURRENT_TERM=4
CURRENT_YEAR=2026


def _visible_text(raw:str)->str:
    raw=re.sub(r"<br\s*/?>"," ",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",html_lib.unescape(raw)).strip()


def _normalize_name(name:str)->str:
    return re.sub(r"\s+","",name)


def _year_table(html:str,year:int)->str:
    marker=re.search(rf"{year}\s*년도?\s*구성현황",html)
    if not marker:
        marker=re.search(rf"{year}\s*년\s*구성현황",html)
    if not marker:
        raise ValueError(f"Missing {year} research-group composition heading")
    m=re.search(r"<table\b[^>]*>[\s\S]*?</table>",html[marker.end():],flags=re.I)
    if not m:
        raise ValueError(f"Missing research-group table after {year} heading")
    return m.group(0)


def _parse_participants(value:str)->list[dict]:
    out=[]
    for raw in re.split(r"\s*,\s*",value):
        item=raw.strip()
        if not item:
            continue
        representative=bool(re.search(r"\(\s*대표\s*\)",item))
        name=re.sub(r"\(\s*대표\s*\)","",item).strip()
        name=_normalize_name(name)
        if not re.fullmatch(r"[가-힣]{2,5}",name):
            raise ValueError(f"Unexpected research-group participant label: {raw!r}")
        out.append({"name":name,"role":"대표" if representative else "회원"})
    if not out:
        raise ValueError("Empty research-group participant list")
    if sum(r["role"]=="대표" for r in out)!=1:
        raise ValueError("Research group must have exactly one representative in source table")
    return out


def parse_groups(html:str,year:int=CURRENT_YEAR)->list[dict]:
    table=_year_table(html,year)
    # The official page may retain older roster drafts inside HTML comments.
    # Only active markup is source-of-truth for the current composition table.
    table=re.sub(r"<!--.*?-->","",table,flags=re.S)
    groups=[]
    for tr in re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>",table,flags=re.I):
        cells=[
            _visible_text(x)
            for x in re.findall(r"<t[dh]\b[^>]*>([\s\S]*?)</t[dh]>",tr,flags=re.I)
        ]
        if len(cells)<4:
            continue
        # Skip header row.
        if any("연구단체명" in c for c in cells):
            continue
        ordinal,group_name,count_text,participants_text=cells[:4]
        if not group_name or not re.search(r"\d+",count_text):
            continue
        expected_count=int(re.search(r"\d+",count_text).group())
        participants=_parse_participants(participants_text)
        if len(participants)!=expected_count:
            raise ValueError(
                f"Research group member-count mismatch: {group_name}: "
                f"table={expected_count}, parsed={len(participants)}"
            )
        group_id="research-group-"+str(year)+"-"+hashlib.sha256(
            group_name.encode("utf-8")
        ).hexdigest()[:12]
        groups.append({
            "group_id":group_id,
            "year":year,
            "ordinal":ordinal or None,
            "group_name":group_name,
            "member_count":expected_count,
            "participants":participants,
            "source_url":URL,
        })
    if not groups:
        raise ValueError(f"No research groups parsed for {year}")
    return groups


def collect(root:Path=ROOT)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    groups=parse_groups(fetch_text(URL),CURRENT_YEAR)

    current=parse_member_index(fetch_text(LIST_URL))
    by_normalized={}
    for row in current:
        key=_normalize_name(row["name"])
        if key in by_normalized:
            raise ValueError(f"Duplicate normalized current member name: {key}")
        by_normalized[key]=row

    group_rows=[]
    memberships=[]
    unresolved=[]
    for group in groups:
        group_rows.append({
            "group_id":group["group_id"],
            "group_name":group["group_name"],
            "council_scope":COUNCIL_SCOPE,
            "term":CURRENT_TERM,
            "year":group["year"],
            "member_count":group["member_count"],
            "activity_end_rule":f"{group['year']}-12-31",
            "activity_start_date":None,
            "activity_end_date":None,
            "period_precision":"year_only",
            "source_url":group["source_url"],
            "checked_at":stamp,
        })
        for item in group["participants"]:
            member=by_normalized.get(_normalize_name(item["name"]))
            if not member:
                unresolved.append({
                    "group_id":group["group_id"],
                    "group_name":group["group_name"],
                    **item,
                })
                continue
            memberships.append({
                "person_id":stable_person_id(member["f_code"]),
                "official_profile_code":member["f_code"],
                "council_scope":COUNCIL_SCOPE,
                "term":CURRENT_TERM,
                "membership_type":"research_group",
                "group_id":group["group_id"],
                "label":group["group_name"],
                "role":item["role"],
                "year":group["year"],
                "start_date":None,
                "end_date":None,
                "period_precision":"year_only",
                "source_url":group["source_url"],
                "checked_at":stamp,
            })

    if unresolved:
        raise ValueError(
            "Unresolved current research-group members: "
            + json.dumps(unresolved,ensure_ascii=False)
        )

    save_json(root/"archive/research_groups/current_groups.json",group_rows)
    save_json(root/"archive/research_groups/current_memberships.json",memberships)
    report={
        "checked_at":stamp,
        "year":CURRENT_YEAR,
        "group_count":len(group_rows),
        "membership_rows":len(memberships),
        "representative_rows":sum(r["role"]=="대표" for r in memberships),
        "unresolved_members":0,
        "groups":[
            {
                "group_name":row["group_name"],
                "member_count":row["member_count"],
            }
            for row in group_rows
        ],
    }
    save_json(root/"reports/current-research-groups.json",report)
    return report


def main():
    print(json.dumps(collect(),ensure_ascii=False))


if __name__=="__main__":
    main()
