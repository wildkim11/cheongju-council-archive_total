"""Build historical committee roster ledgers from reviewed official source registry.

Only registry rows marked verified_full_roster_text are promotable.
Partial/candidate sources remain non-promoting evidence.
"""
from __future__ import annotations
import datetime as dt
import html as html_lib
import json
import re
from pathlib import Path

from archive_common import save_json, sha256_bytes
from collect_current_members import fetch_text, LIST_URL, parse_member_index, stable_person_id
from collect_integrated_historical_members import (
    HISTORICAL_TERMS,
    Session,
    fetch_term_html,
    parse_term_members,
    person_id as historical_person_id,
)

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"config/historical_committee_sources.json"
COUNCIL_SCOPE="cheongju_integrated"
CURRENT_TERM=4

def _visible(raw:str)->str:
    raw=re.sub(r"<br\s*/?>"," ",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",html_lib.unescape(raw)).strip()

def _split_names(value:str)->list[str]:
    value=re.sub(r"\([^)]*\)"," ",value)
    parts=re.split(r"\s*[,·ㆍ]\s*|\s{2,}",value)
    out=[]
    for p in parts:
        for name in re.findall(r"[가-힣]{2,5}",p):
            if name not in {"위원장","부위원장","위원","위원회","청주시의회"} and name not in out:
                out.append(name)
    return out

def _committee_type(name:str)->str:
    compact=re.sub(r"\s+","",name)
    return "special_committee" if "특별위원회" in compact else "standing_committee"

def _parse_table_rows(html:str)->list[dict]:
    rows=[]
    for tr in re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>",html,flags=re.I):
        cells=[_visible(x) for x in re.findall(r"<t[dh]\b[^>]*>([\s\S]*?)</t[dh]>",tr,flags=re.I)]
        if len(cells)<3:
            continue
        joined=" ".join(cells)
        if "위원회" not in joined or ("위원장" in joined and "부위원장" in joined and len(cells)<=4 and not re.search(r"[가-힣]{2,5}\s*[,·ㆍ]",joined)):
            # header-like rows are ignored unless they also contain roster names
            if any(x in joined for x in ("위원회 명","위원회명")):
                continue
        name_cell=cells[0]
        m=re.search(r"(.+?위원회)(?:\s*\(\s*\d+\s*\))?$",name_cell)
        if not m:
            continue
        committee_name=re.sub(r"\s+"," ",m.group(1)).strip()
        chair=cells[1].strip() if len(cells)>1 else ""
        vice=cells[2].strip() if len(cells)>2 else ""
        members=" ".join(cells[3:]) if len(cells)>3 else ""
        parsed=[]
        for role,value in (("위원장",chair),("부위원장",vice)):
            names=_split_names(value)
            if len(names)==1:
                parsed.append({"name":names[0],"role":role})
        for name in _split_names(members):
            parsed.append({"name":name,"role":"위원"})
        if parsed:
            rows.append({"committee_name":committee_name,"participants":parsed})
    return rows

def _parse_text_rows(html:str)->list[dict]:
    text=_visible(html)
    out=[]
    pattern=re.compile(
        r"([가-힣·ㆍ\s]+위원회)\s*\(\s*(\d+)\s*\)\s+"
        r"([가-힣]{2,5})\s+([가-힣]{2,5})\s+"
        r"(.+?)(?=(?:[가-힣·ㆍ\s]+위원회\s*\(\s*\d+\s*\))|$)"
    )
    for m in pattern.finditer(text):
        committee_name=re.sub(r"\s+"," ",m.group(1)).strip()
        expected=int(m.group(2))
        chair=m.group(3); vice=m.group(4)
        participants=[
            {"name":chair,"role":"위원장"},
            {"name":vice,"role":"부위원장"},
        ]
        seen={chair,vice}
        for name in _split_names(m.group(5)):
            if name not in seen:
                participants.append({"name":name,"role":"위원"});seen.add(name)
        if len(participants)==expected:
            out.append({
                "committee_name":committee_name,
                "expected_count":expected,
                "participants":participants,
            })
    return out

def parse_rosters(html:str)->list[dict]:
    rows=_parse_table_rows(html)
    if not rows:
        rows=_parse_text_rows(html)
    # Enforce printed counts when recoverable from committee label text.
    dedup={}
    for row in rows:
        key=row["committee_name"]
        people=[]
        seen=set()
        for p in row["participants"]:
            if p["name"] in seen: continue
            seen.add(p["name"]);people.append(p)
        row["participants"]=people
        dedup[key]=row
    return list(dedup.values())

def _identity_map(term:int)->dict[str,str]:
    by_name={}
    if term==CURRENT_TERM:
        for row in parse_member_index(fetch_text(LIST_URL)):
            if row["name"] in by_name:
                raise ValueError(f"Duplicate current name: {row['name']}")
            by_name[row["name"]]=stable_person_id(row["f_code"])
        return by_name

    if term not in HISTORICAL_TERMS:
        raise ValueError(f"Unsupported integrated term identity scope: {term}")
    session=Session()
    for row in parse_term_members(fetch_term_html(term,session),term):
        name=row["name"]
        pid=historical_person_id(row)
        if name in by_name and by_name[name]!=pid:
            raise ValueError(f"Ambiguous historical name in term {term}: {name}")
        by_name[name]=pid
    return by_name

def _source_period(source:dict,committee_name:str)->tuple[str|None,str|None,str]:
    periods=source.get("committee_periods") or {}
    p=periods.get(committee_name)
    if p:
        return p.get("start_date"),p.get("end_date"),p.get("period_precision","exact_date")
    return (
        source.get("effective_start_date"),
        source.get("effective_end_date"),
        source.get("period_precision","unknown"),
    )

def collect(root:Path=ROOT)->dict:
    registry=json.loads(REGISTRY.read_text(encoding="utf-8"))
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    promotable=[
        x for x in registry["sources"]
        if x.get("source_status")=="verified_full_roster_text"
    ]
    memberships=[];committee_states=[];skipped=[];identity_cache={}
    for source in promotable:
        term=int(source["term"])
        html=fetch_text(source["official_url"])
        rosters=parse_rosters(html)
        if not rosters:
            raise ValueError(f"No full roster parsed from verified source {source['source_id']}")
        by_name=identity_cache.setdefault(term,_identity_map(term))
        for roster in rosters:
            start,end,precision=_source_period(source,roster["committee_name"])
            unresolved=[p["name"] for p in roster["participants"] if p["name"] not in by_name]
            if unresolved:
                raise ValueError(
                    f"{source['source_id']} {roster['committee_name']}: unresolved names {unresolved}"
                )
            state_id="committee-state-"+sha256_bytes(
                f"{source['source_id']}|{roster['committee_name']}|{start or ''}".encode()
            )[:16]
            committee_states.append({
                "state_id":state_id,
                "council_scope":COUNCIL_SCOPE,
                "term":term,
                "phase":source.get("phase"),
                "committee_name":roster["committee_name"],
                "committee_type":_committee_type(roster["committee_name"]),
                "start_date":start,
                "end_date":end,
                "period_precision":precision,
                "source_id":source["source_id"],
                "source_url":source["official_url"],
                "source_date":source.get("source_date"),
                "checked_at":stamp,
                "member_count":len(roster["participants"]),
            })
            for p in roster["participants"]:
                memberships.append({
                    "state_id":state_id,
                    "person_id":by_name[p["name"]],
                    "person_name":p["name"],
                    "council_scope":COUNCIL_SCOPE,
                    "term":term,
                    "membership_type":_committee_type(roster["committee_name"]),
                    "label":roster["committee_name"],
                    "role":p["role"],
                    "start_date":start,
                    "end_date":end,
                    "period_precision":precision,
                    "source_id":source["source_id"],
                    "source_url":source["official_url"],
                    "checked_at":stamp,
                })
    for source in registry["sources"]:
        if source.get("source_status")!="verified_full_roster_text":
            skipped.append({
                "source_id":source["source_id"],
                "source_status":source.get("source_status"),
                "reason":"not_promotable_full_roster",
            })
    committee_states.sort(key=lambda r:(r["term"],r.get("start_date") or "",r["committee_name"]))
    memberships.sort(key=lambda r:(r["term"],r.get("start_date") or "",r["label"],r["role"],r["person_name"]))
    save_json(root/"archive/committees/historical_states.json",committee_states)
    save_json(root/"archive/committees/historical_memberships.json",memberships)
    report={
        "checked_at":stamp,
        "promoted_sources":len(promotable),
        "committee_states":len(committee_states),
        "membership_rows":len(memberships),
        "skipped_sources":skipped,
        "by_term":{},
    }
    for row in committee_states:
        report["by_term"][str(row["term"])]=report["by_term"].get(str(row["term"]),0)+1
    save_json(root/"reports/historical-committees.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(collect(),ensure_ascii=False))
