"""Build non-promoting identity-resolution candidates across archived person records.

This script never merges person IDs. It only emits evidence candidates.
"""
from __future__ import annotations
import datetime as dt, json, re
from pathlib import Path
from archive_common import save_json

ROOT=Path(__file__).resolve().parents[1]

PERSON_SOURCES=[
    ("current",ROOT/"archive/people/people.json"),
    ("integrated_history",ROOT/"archive/people/history/cheongju_integrated_people.json"),
    ("old_city",ROOT/"archive/people/history/cheongju_old_city_people_candidates.json"),
    ("old_county",ROOT/"archive/people/history/cheongwon_old_county_people_candidates.json"),
]

def _load(path:Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

def _norm_name(name:str)->str:
    return re.sub(r"\s+","",name or "")

def build(root:Path=ROOT)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    records=[]
    for source,path0 in PERSON_SOURCES:
        path=root/path0.relative_to(ROOT)
        for row in _load(path):
            records.append({**row,"_source_family":source})

    candidates=[]
    # Strong official-code candidates.
    by_code={}
    for r in records:
        code=r.get("official_profile_code")
        ctype=r.get("official_profile_code_type") or ("f_code" if code and r.get("person_id","").startswith("person-fcode-") else None)
        if code and ctype=="f_code":
            by_code.setdefault(("f_code",str(code)),[]).append(r)
    for (ctype,code),rows in by_code.items():
        ids=sorted({r["person_id"] for r in rows})
        if len(ids)>1:
            candidates.append({
                "candidate_type":"official_code_match",
                "evidence_strength":"strong",
                "official_code_type":ctype,
                "official_code":code,
                "person_ids":ids,
                "names":sorted({_norm_name(r.get("name")) for r in rows}),
                "source_families":sorted({r["_source_family"] for r in rows}),
                "promotion_status":"review_required",
            })

    # Name-based candidates are weak and never auto-promoted.
    by_name={}
    for r in records:
        n=_norm_name(r.get("name"))
        if n:
            by_name.setdefault(n,[]).append(r)
    for name,rows in by_name.items():
        ids=sorted({r["person_id"] for r in rows})
        if len(ids)<2: continue
        candidate={
            "candidate_type":"same_normalized_name",
            "evidence_strength":"weak",
            "normalized_name":name,
            "person_ids":ids,
            "source_families":sorted({r["_source_family"] for r in rows}),
            "official_profile_codes":sorted({
                str(r.get("official_profile_code")) for r in rows if r.get("official_profile_code")
            }),
            "portrait_source_urls":sorted({
                (r.get("portrait") or {}).get("source_url") or r.get("portrait_source_url")
                for r in rows
                if ((r.get("portrait") or {}).get("source_url") or r.get("portrait_source_url"))
            }),
            "promotion_status":"review_required",
        }
        candidates.append(candidate)

    # Deduplicate exact candidate signatures.
    uniq={}
    for c in candidates:
        key=(c["candidate_type"],tuple(c["person_ids"]),c.get("official_code"))
        uniq[key]=c
    rows=sorted(uniq.values(),key=lambda c:(c["candidate_type"],c.get("normalized_name",""),c.get("official_code","")))
    save_json(root/"archive/people/identity_candidates.json",rows)
    report={
        "checked_at":stamp,
        "person_source_records":len(records),
        "candidate_rows":len(rows),
        "strong_official_code_candidates":sum(c["candidate_type"]=="official_code_match" for c in rows),
        "weak_same_name_candidates":sum(c["candidate_type"]=="same_normalized_name" for c in rows),
        "automatic_merges":0,
    }
    save_json(root/"reports/identity-candidates.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(build(),ensure_ascii=False))
