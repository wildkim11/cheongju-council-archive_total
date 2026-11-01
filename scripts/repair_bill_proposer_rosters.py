"""Repair populated bill proposer arrays using term-scoped official member names.

No source-site requests are made. Raw parsed text is preserved for provenance.
"""
from __future__ import annotations
import datetime as dt, json, re
from pathlib import Path
from archive_common import save_json

ROOT=Path(__file__).resolve().parents[1]
COUNCIL_SCOPE="cheongju_integrated"

STOP_LABELS=[
    "공동발의","위원회회부일","위원회 회부일","상임위원회","본회의회부일","본회의 회부일",
    "본회의","상정일","처리일","처리결과","집행기관","이송일","공포일","공포번호",
    "철회일자","철회일","비고","첨부파일","기타파일"
]

def _load(path:Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

def _norm(value:str|None)->str:
    return re.sub(r"\s+","",value or "")

def _cut(value:str|None,labels:list[str])->str:
    text=value or ""
    compact=_norm(text)
    positions=[]
    for label in labels:
        p=compact.find(_norm(label))
        if p>=0:
            positions.append(p)
    if not positions:
        return compact
    return compact[:min(positions)]

def build_term_names(root:Path=ROOT)->dict[int,list[str]]:
    people={}
    for p in _load(root/"archive/people/people.json")+_load(root/"archive/people/history/cheongju_integrated_people.json"):
        people[p["person_id"]]=p.get("name")

    names={}
    for t in _load(root/"archive/people/tenures.json")+_load(root/"archive/people/history/cheongju_integrated_tenures.json"):
        if t.get("council_scope")!=COUNCIL_SCOPE:
            continue
        name=people.get(t.get("person_id"))
        if name:
            names.setdefault(int(t["term"]),set()).add(_norm(name))

    # Dated historical committee states can contain members who later left the
    # current term roster. Preserve them as valid term-name evidence.
    for m in _load(root/"archive/committees/historical_memberships.json"):
        if m.get("council_scope")!=COUNCIL_SCOPE:
            continue
        name=m.get("person_name")
        if name:
            names.setdefault(int(m["term"]),set()).add(_norm(name))

    return {term:sorted(vals,key=lambda x:(-len(x),x)) for term,vals in names.items()}

def _match_names(segment:str,names:list[str])->list[str]:
    found=[]
    for name in names:
        if name and name in segment and name not in found:
            found.append(name)
    # preserve source order where possible
    found.sort(key=lambda n:segment.find(n))
    return found

def repair(root:Path=ROOT)->dict:
    path=root/"archive/bills/items.json"
    rows=_load(path)
    if not rows:
        raise ValueError("No populated bills")
    term_names=build_term_names(root)
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()

    stats={
        "bill_records":len(rows),
        "member_bills":0,
        "nonmember_bills":0,
        "member_bills_with_names":0,
        "member_bills_without_names":0,
        "nonmember_names_cleared":0,
        "representative_rows":0,
        "co_proposer_rows":0,
        "unknown_proposer_type_rows":0,
    }
    unknown_types=[]

    for row in rows:
        list_type=_norm(row.get("proposer_type_list"))
        detail_type=_norm(row.get("proposer_type"))
        proposer_type=list_type or detail_type
        row["proposer_type"]=row.get("proposer_type_list") or row.get("proposer_type")
        row["proposer_roster_repaired_at"]=stamp
        row["proposer_roster_repair_method"]="term_name_match_on_preserved_raw_text"

        if proposer_type!="의원":
            stats["nonmember_bills"]+=1
            if row.get("full_proposer_names"):
                stats["nonmember_names_cleared"]+=1
            row["representative_proposers"]=[]
            row["co_proposers"]=[]
            row["full_proposer_names"]=[]
            row["proposer_roster_parse_status"]="not_applicable_nonmember"
            if proposer_type not in {"시장","의장","위원장","위원회","기타",""}:
                stats["unknown_proposer_type_rows"]+=1
                unknown_types.append({"internal_number":row["internal_number"],"term":row["term"],"value":proposer_type})
            continue

        stats["member_bills"]+=1
        names=term_names.get(int(row["term"]),[])
        rep_raw=row.get("representative_proposer_text")
        co_raw=row.get("co_proposers_text")

        rep_segment=_cut(rep_raw,STOP_LABELS)
        co_segment=_cut(co_raw,[x for x in STOP_LABELS if x!="공동발의"])
        reps=_match_names(rep_segment,names)
        co=_match_names(co_segment,names)

        # A name found in the representative field takes precedence.
        co=[n for n in co if n not in reps]
        full=[]
        for n in reps+co:
            if n not in full:
                full.append(n)

        row["representative_proposers"]=reps
        row["co_proposers"]=co
        row["full_proposer_names"]=full
        row["proposer_roster_parse_status"]="matched_term_names" if full else "needs_source_reparse"
        row["proposer_roster_rep_segment_normalized"]=rep_segment
        row["proposer_roster_co_segment_normalized"]=co_segment

        stats["representative_rows"]+=len(reps)
        stats["co_proposer_rows"]+=len(co)
        if full:
            stats["member_bills_with_names"]+=1
        else:
            stats["member_bills_without_names"]+=1

    save_json(path,rows)
    report={
        "checked_at":stamp,
        **stats,
        "unknown_proposer_type_examples":unknown_types[:50],
        "acceptance":{
            "nonmember_person_names_zero":all(
                not r.get("full_proposer_names")
                for r in rows
                if _norm(r.get("proposer_type_list") or r.get("proposer_type"))!="의원"
            ),
        }
    }
    save_json(root/"reports/bill-proposer-repair.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(repair(),ensure_ascii=False,indent=2))
