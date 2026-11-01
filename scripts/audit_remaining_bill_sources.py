"""Read-only 2026-11-02 QA for remaining eight and five institutional bill anomalies.

Produces a finite, source-linked exception ledger. It never modifies the bill,
proposer membership, or analyzer export datasets. It does not equate a name in
a procedural record with a personal bill proposer.
"""
from __future__ import annotations
import collections
import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REMAINING=("1308","1458","1960","2083","2258","2364","2637","3255")
INSTITUTIONAL=("375","2177","2180","3265","3266")
FIELDS=("internal_number","bill_number","term","title","bill_type","proposer_type_list","proposer_type","session","proposal_date","processed_date_list","committee","result_list","official_url","list_source_url","representative_proposer_text","co_proposers_text","representative_proposers","co_proposers","full_proposer_names","proposer_roster_parse_status","proposer_roster_repair_method","proposer_roster_rep_segment_normalized","proposer_roster_co_segment_normalized","proposer_roster_minutes_evidence")

def load(root, rel):
    return json.loads((root/rel).read_text(encoding="utf-8"))

def summarize(root=ROOT):
    items=load(root,"archive/bills/items.json")
    links=load(root,"archive/bills/proposer_memberships.json")
    report=load(root,"reports/bill-data-audit.json")
    minutes=load(root,"reports/bill-minutes-proposer-evidence.json")
    by_id={str(x.get("internal_number")):x for x in items}
    if len(by_id)!=len(items):
        raise ValueError("Bill IDs not unique")
    missing={str(x["internal_number"]) for x in report["member_bills_without_names"]}
    if missing!=set(REMAINING):
        raise ValueError(f"Remaining bill inventory changed: {sorted(missing)}")
    pending={str(x["internal_number"]):x for x in minutes["records"]}
    by_bill=collections.defaultdict(list)
    for link in links:
        by_bill[str(link["internal_number"])].append(link)
    if len(links)!=11408:
        raise ValueError(f"Expected validated snapshot of 11408 relationships, got {len(links)}")

    resolved=[]
    for id in REMAINING:
        b=by_id[id]
        if b.get("full_proposer_names"):
            raise ValueError(f"Unresolved member bill already has names: {id}")
        ev=pending.get(id,{})
        # Evidence may be used to guide human review, but not to auto-promote a roster.
        resolved.append({
            "internal_number":id,
            "raw_bill_fields":{k:b.get(k) for k in FIELDS if k in b},
            "minutes_review_status":ev.get("status"),
            "representative_mentions":ev.get("representatives_mentioned",[]),
            "minutes_evidence":[{
                k:v for k,v in match.items()
                if k in ("meeting_id","meeting_url","meeting_date","publication_status","evidence_type","representative","all_names","source_excerpt","every_name_unique_same_term")
            } for match in ev.get("evidence",[])],
            "existing_person_link_count":len(by_bill[id]),
            "conclusion":"NO_FULL_ROSTER_VERIFIED__NO_PERSONAL_RELATIONSHIP_PROMOTION",
        })

    institutions=[]
    link_count=0
    for id in INSTITUTIONAL:
        bill=by_id[id]
        selected=by_bill[id]
        if bill.get("proposer_type")=="의원" or bill.get("proposer_type_list")=="의원":
            raise ValueError(f"Institutional record mislabeled as personal in primary fields: {id}")
        if not selected:
            raise ValueError(f"Expected institutional-linked anomaly missing: {id}")
        link_count+=len(selected)
        institutions.append({
            "internal_number":id,
            "raw_bill_fields":{k:bill.get(k) for k in FIELDS if k in bill},
            "relationships":[
                {k:v for k,v in x.items() if k in ("person_name","proposer_role","person_id","resolution_status","source_url","term","bill_number")}
                for x in selected
            ],
            "relationships_count":len(selected),
            "relationship_names_equal_bill_roster":set(x["person_name"] for x in selected)==set(bill.get("full_proposer_names") or []),
            "conclusion":"EXISTING_RELATIONSHIP_TYPE_CONFLICT__SOURCE_ROLE_UNVERIFIED",
        })
    if link_count!=44:
        raise ValueError(f"Expected 44 institutional person links, got {link_count}")

    nonmembers={str(b["internal_number"]) for b in items
                if "의원" not in str(b.get("proposer_type_list") or b.get("proposer_type") or "")}
    all_anomaly_keys={key for key in nonmembers if by_bill[key]}
    if all_anomaly_keys!=set(INSTITUTIONAL):
        raise ValueError(f"Found additional institutional person links: {sorted(all_anomaly_keys-set(INSTITUTIONAL))}")

    return {
        "checked_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope":"offline read-only snapshot examination; official website and original attachments not re-fetched",
        "bill_records":len(items),
        "person_relationships":len(links),
        "pending_member_bill_count":len(resolved),
        "institutional_bill_anomaly_count":len(institutions),
        "institutional_person_relationships":link_count,
        "member_bills":resolved,
        "institutional_anomalies":institutions,
        "data_writes_to_canonical_archive":0,
        "classification_limit":"Original bill list type outranks presence of names in extracted detail. Meeting records name mention alone is not proposer-roster proof.",
    }

if __name__=="__main__":
    data=summarize()
    out=ROOT/"reports/bill-pending-and-institutional-source-qa.json"
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "bill_records":data["bill_records"],
        "pending_member_bill_count":data["pending_member_bill_count"],
        "institutional_bill_anomaly_count":data["institutional_bill_anomaly_count"],
        "institutional_person_relationships":data["institutional_person_relationships"],
        "member_bills":[{
            "id":x["internal_number"],
            "status":x["minutes_review_status"],
            "representative_mentions":x["representative_mentions"],
            "minutes_evidence_count":len(x["minutes_evidence"])
        } for x in data["member_bills"]],
        "institutional_anomalies":[{
            "id":x["internal_number"],
            "term":x["raw_bill_fields"].get("term"),
            "title":x["raw_bill_fields"].get("title"),
            "type_list":x["raw_bill_fields"].get("proposer_type_list"),
            "type_detail":x["raw_bill_fields"].get("proposer_type"),
            "names":x["raw_bill_fields"].get("full_proposer_names"),
            "relationships":x["relationships_count"],
            "representatives":x["raw_bill_fields"].get("representative_proposers"),
            "co_proposers":x["raw_bill_fields"].get("co_proposers"),
            "raw_rep_text":x["raw_bill_fields"].get("representative_proposer_text"),
            "raw_co_text":x["raw_bill_fields"].get("co_proposers_text")
        } for x in data["institutional_anomalies"]],
    },ensure_ascii=False,indent=2))
