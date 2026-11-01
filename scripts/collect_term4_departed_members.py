"""Collect current-term historical-only members who no longer appear in the active roster.

This is a small delta collector used after Stage A. A historical term-4 row is
considered the same active person only when name matches plus either district
or official portrait filename. Name alone never suppresses a historical row.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import urllib.parse
from pathlib import Path

from archive_common import save_json, sha256_bytes
from collect_integrated_historical_members import (
    COUNCIL_SCOPE, CURRENT_TERM, Session, URL, fetch_term_html,
    parse_term_members, person_id, _portrait_extension,
)

ROOT=Path(__file__).resolve().parents[1]

def _norm(value:str|None)->str:
    return re.sub(r"\s+","",value or "")

def _portrait_key(url:str|None)->str|None:
    if not url:
        return None
    return Path(urllib.parse.urlsplit(url).path).name.lower()

def collect(root:Path=ROOT,save_portraits:bool=True)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    people_path=root/"archive/people/people.json"
    districts_path=root/"archive/people/district_memberships.json"
    if not people_path.exists() or not districts_path.exists():
        raise ValueError("Current member archive must exist before term-4 delta collection")

    current_people=json.loads(people_path.read_text(encoding="utf-8"))
    current_districts=json.loads(districts_path.read_text(encoding="utf-8"))
    districts_by_pid={}
    for item in current_districts:
        districts_by_pid.setdefault(item.get("person_id"),set()).add(
            _norm(item.get("district") or item.get("label"))
        )

    session=Session()
    term_rows=parse_term_members(fetch_term_html(CURRENT_TERM,session),CURRENT_TERM)

    def matches_active(row:dict)->bool:
        row_district=_norm(row.get("district"))
        row_photo=_portrait_key(row.get("portrait_source_url"))
        for active in current_people:
            if active.get("name")!=row.get("name"):
                continue
            same_district=bool(
                row_district and row_district in districts_by_pid.get(active.get("person_id"),set())
            )
            same_photo=bool(
                row_photo and row_photo==_portrait_key((active.get("portrait") or {}).get("source_url"))
            )
            if same_district or same_photo:
                return True
        return False

    historical_only=[row for row in term_rows if not matches_active(row)]
    people=[];tenures=[];districts=[]
    for row in historical_only:
        pid=person_id(row)
        portrait=None
        if row.get("portrait_source_url"):
            if save_portraits:
                raw,ctype=session.request(row["portrait_source_url"])
                ext=_portrait_extension(ctype,row["portrait_source_url"])
                local_path=f"archive/people/portraits/{pid}{ext}"
                path=root/local_path
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(raw)
                portrait={
                    "source_url":row["portrait_source_url"],
                    "local_path":local_path,
                    "checked_at":stamp,
                    "sha256":sha256_bytes(raw),
                }
            else:
                portrait={
                    "source_url":row["portrait_source_url"],
                    "local_path":None,
                    "checked_at":stamp,
                    "sha256":None,
                }
        precision="exact_date" if row.get("start_date") and row.get("end_date") else "term_only"
        people.append({
            "person_id":pid,
            "identity_status":"candidate_unmerged",
            "name":row["name"],
            "aliases":[],
            "official_profile_url":row.get("official_profile_url"),
            "official_profile_code":row.get("official_profile_code"),
            "official_profile_code_type":row.get("official_profile_code_type"),
            "portrait":portrait,
            "source_url":URL,
            "checked_at":stamp,
            "historical_only_current_term":True,
        })
        tenures.append({
            "person_id":pid,
            "council_scope":COUNCIL_SCOPE,
            "term":CURRENT_TERM,
            "start_date":row.get("start_date"),
            "end_date":row.get("end_date"),
            "period_precision":precision,
            "source_url":URL,
            "checked_at":stamp,
            "historical_only_current_term":True,
        })
        if row.get("district"):
            districts.append({
                "person_id":pid,
                "council_scope":COUNCIL_SCOPE,
                "term":CURRENT_TERM,
                "membership_type":"district",
                "label":row["district"],
                "role":None,
                "start_date":row.get("start_date"),
                "end_date":row.get("end_date"),
                "period_precision":precision,
                "source_url":URL,
                "checked_at":stamp,
                "historical_only_current_term":True,
            })

    people.sort(key=lambda r:(r["name"],r["person_id"]))
    tenures.sort(key=lambda r:r["person_id"])
    districts.sort(key=lambda r:r["person_id"])
    save_json(root/"archive/people/history/cheongju_integrated_term4_departed_people.json",people)
    save_json(root/"archive/people/history/cheongju_integrated_term4_departed_tenures.json",tenures)
    save_json(root/"archive/people/history/cheongju_integrated_term4_departed_district_memberships.json",districts)

    report={
        "checked_at":stamp,
        "council_scope":COUNCIL_SCOPE,
        "term":CURRENT_TERM,
        "official_term_roster_rows":len(term_rows),
        "current_active_rows":len(current_people),
        "historical_only_rows":len(people),
        "historical_only_names":[p["name"] for p in people],
        "identity_rule":"same_name_plus_district_or_portrait_for_active_match",
    }
    save_json(root/"reports/cheongju_integrated-term4-historical-only.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(collect(),ensure_ascii=False))
