"""Resolve official bill proposer names to term-scoped archive person IDs.

This is source identity linkage, not an analytical relationship score.
Only exact unique matches within the same council scope + term are promoted.
"""
from __future__ import annotations
import datetime as dt, json
from pathlib import Path
from archive_common import save_json

ROOT=Path(__file__).resolve().parents[1]
COUNCIL_SCOPE="cheongju_integrated"

def _load(path:Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

def build_term_name_index(root:Path=ROOT)->dict[int,dict[str,list[str]]]:
    people={}
    for path in [
        root/"archive/people/people.json",
        root/"archive/people/history/cheongju_integrated_people.json",
        root/"archive/people/history/cheongju_integrated_term4_departed_people.json",
    ]:
        for p in _load(path):
            people[p["person_id"]]=p

    idx={}
    tenure_paths=[
        root/"archive/people/tenures.json",
        root/"archive/people/history/cheongju_integrated_tenures.json",
        root/"archive/people/history/cheongju_integrated_term4_departed_tenures.json",
    ]
    for path in tenure_paths:
        for t in _load(path):
            if t.get("council_scope")!=COUNCIL_SCOPE:
                continue
            pid=t.get("person_id")
            person=people.get(pid)
            if not person or not person.get("name"):
                continue
            term=int(t["term"])
            idx.setdefault(term,{}).setdefault(person["name"],[])
            if pid not in idx[term][person["name"]]:
                idx[term][person["name"]].append(pid)
    return idx

def resolve_name(index:dict[int,dict[str,list[str]]],term:int,name:str)->dict:
    ids=index.get(term,{}).get(name,[])
    if len(ids)==1:
        return {"status":"resolved_exact_term","person_id":ids[0]}
    if len(ids)>1:
        return {"status":"ambiguous_same_term","candidate_person_ids":ids}
    return {"status":"unresolved","candidate_person_ids":[]}

def link(root:Path=ROOT)->dict:
    bills_path=root/"archive/bills/items.json"
    bills=_load(bills_path)
    if not bills:
        raise ValueError("Bill archive is empty; collect bills first")
    index=build_term_name_index(root)
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()

    rows=[];unresolved=[];ambiguous=[]
    for bill in bills:
        term=int(bill["term"])
        reps=set(bill.get("representative_proposers") or [])
        co=set(bill.get("co_proposers") or [])
        for name in bill.get("full_proposer_names") or []:
            resolved=resolve_name(index,term,name)
            role="representative" if name in reps else "co_proposer" if name in co else "proposer"
            row={
                "internal_number":bill["internal_number"],
                "bill_number":bill.get("bill_number"),
                "title":bill.get("title"),
                "council_scope":COUNCIL_SCOPE,
                "term":term,
                "person_name":name,
                "proposer_role":role,
                "resolution_status":resolved["status"],
                "person_id":resolved.get("person_id"),
                "candidate_person_ids":resolved.get("candidate_person_ids",[]),
                "source_url":bill["official_url"],
                "checked_at":stamp,
            }
            rows.append(row)
            if row["resolution_status"]=="unresolved": unresolved.append(row)
            elif row["resolution_status"]=="ambiguous_same_term": ambiguous.append(row)

    save_json(root/"archive/bills/proposer_memberships.json",rows)
    report={
        "checked_at":stamp,
        "bill_records":len(bills),
        "proposer_rows":len(rows),
        "resolved_exact_term":sum(r["resolution_status"]=="resolved_exact_term" for r in rows),
        "unresolved":len(unresolved),
        "ambiguous_same_term":len(ambiguous),
        "unresolved_examples":[
            {"term":r["term"],"name":r["person_name"],"internal_number":r["internal_number"]}
            for r in unresolved[:20]
        ],
    }
    save_json(root/"reports/bill-proposer-identity-links.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(link(),ensure_ascii=False))
