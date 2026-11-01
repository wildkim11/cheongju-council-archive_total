"""Audit populated bill/proposer data without contacting official sources."""
from __future__ import annotations
import collections, datetime as dt, json, re
from pathlib import Path
from archive_common import save_json

ROOT=Path(__file__).resolve().parents[1]

def _load(path:Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

def _norm_type(value:str|None)->str:
    return re.sub(r"\s+","",value or "") or "(blank)"

def audit(root:Path=ROOT)->dict:
    bills=_load(root/"archive/bills/items.json")
    links=_load(root/"archive/bills/proposer_memberships.json")
    if not bills:
        raise ValueError("No populated bill archive")

    type_counts=collections.Counter(_norm_type(x.get("proposer_type") or x.get("proposer_type_list")) for x in bills)
    by_term=collections.Counter(str(x.get("term")) for x in bills)
    member_bills=[x for x in bills if "의원" in _norm_type(x.get("proposer_type") or x.get("proposer_type_list"))]
    nonmember_with_names=[
        x for x in bills
        if "의원" not in _norm_type(x.get("proposer_type") or x.get("proposer_type_list"))
        and (x.get("full_proposer_names") or [])
    ]

    status_counts=collections.Counter(x.get("resolution_status") or "(missing)" for x in links)
    unresolved=collections.Counter(x.get("person_name") or "" for x in links if x.get("resolution_status")=="unresolved")
    suspicious=[
        {"token":name,"count":count}
        for name,count in unresolved.most_common(100)
        if name
    ]

    member_ids={str(x["internal_number"]) for x in member_bills}
    member_without_names=[
        {
            "internal_number":x.get("internal_number"),
            "term":x.get("term"),
            "bill_number":x.get("bill_number"),
            "title":x.get("title"),
            "session":x.get("session"),
            "proposal_date":x.get("proposal_date"),
            "processed_date":x.get("processed_date_list"),
            "official_url":x.get("official_url"),
            "representative_proposer_text":x.get("representative_proposer_text"),
            "co_proposers_text":x.get("co_proposers_text"),
        }
        for x in member_bills if not (x.get("full_proposer_names") or [])
    ]
    member_links=[x for x in links if str(x.get("internal_number")) in member_ids]
    nonmember_links=[x for x in links if str(x.get("internal_number")) not in member_ids]

    report={
        "checked_at":dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(),
        "bill_records":len(bills),
        "by_term":dict(sorted(by_term.items(),key=lambda x:int(x[0]))),
        "by_proposer_type":dict(type_counts.most_common()),
        "member_proposed_bills":len(member_bills),
        "nonmember_bills":len(bills)-len(member_bills),
        "bills_with_any_full_proposer_names":sum(bool(x.get("full_proposer_names")) for x in bills),
        "nonmember_bills_with_person_names":len(nonmember_with_names),
        "proposer_link_rows":len(links),
        "link_status_counts":dict(status_counts),
        "member_bill_link_rows":len(member_links),
        "nonmember_bill_link_rows":len(nonmember_links),
        "unresolved_top_tokens":suspicious,
        "member_bills_without_names":member_without_names,
        "acceptance":{
            "nonmember_bills_with_person_names_should_be_zero":len(nonmember_with_names)==0,
            "nonmember_bill_link_rows_should_be_zero":len(nonmember_links)==0,
        },
    }
    save_json(root/"reports/bill-data-audit.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
