"""One-time guarded, non-destructive promotion of official 1960 proposer roster.

Strictly verifies official committee minutes-2530 by term, session, date, title,
an adjacent explicit full roster, and unique term-scoped person identities.
Source rows remain unchanged except adding derived provenance/roster facts.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path

from archive_common import save_json
from audit_bill_archive import audit
from audit_stage_c import audit as audit_meetings
from export_analyzer import export
from link_bill_proposers import link, build_term_name_index
from promote_verified_bill_rosters import promote_one
from reconcile_bill_proposers_from_minutes import search_minutes_for_bill
from validate_archive import validate

ROOT=Path(__file__).resolve().parents[1]
ID="1960"
EXPECTED_NAMES={"박노학","김기동","윤여일","최동식","김성택","정태훈","이우균","유광욱","박정희","김용규","박완희","김미자","김태수"}
SOURCE_MEETING_ID="cheongju_integrated:minutes-2530"

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def promote(root=ROOT):
    items_path=root/"archive/bills/items.json"
    items=read(items_path)
    indexed={str(x.get("internal_number")):x for x in items}
    if len(items)!=3394 or len(indexed)!=3394:
        raise ValueError("Unexpected bill archive baseline")
    row=indexed[ID]
    if row.get("term")!=2 or "66" not in str(row.get("session")):
        raise ValueError("Official bill term/session mismatch")
    if row.get("full_proposer_names") or row.get("representative_proposers"):
        raise ValueError("Do not rerun one-time promotion on an already-complete item")
    if (row.get("proposer_type_list") or row.get("proposer_type"))!="의원":
        raise ValueError("Refusing nonmember roster promotion")
    missing=read(root/"reports/bill-data-audit.json")["member_bills_without_names"]
    if {str(x["internal_number"]) for x in missing}!={"1308","1458","1960","2083","2258","2364","2637","3255"}:
        raise ValueError("Remaining bill baseline differs")

    original_institutions={key:indexed[key].copy() for key in ("375","2177","2180","3265","3266")}
    meetings=read(root/"indexes/integrated/meetings.json")
    by_meeting={m["meeting_id"]:m for m in meetings}
    official=by_meeting[SOURCE_MEETING_ID]
    if official["date"]!="2021-10-19" or official["term"]!=2 or official.get("publication_status")!="published":
        raise ValueError("Wrong official committee meeting provenance")
    evidence=search_minutes_for_bill(
        {
            "term":2,
            "title":row["title"],
            "session":row["session"],
            "proposal_date":row["proposal_date"],
            "processed_date":row.get("processed_date_list") or "2021-10-22",
        },
        meetings,root,build_term_name_index(root),{},
    )
    full=[x for x in evidence if x["evidence_type"]=="complete_explicit_roster"]
    if not full or not any(x["meeting_id"]==SOURCE_MEETING_ID for x in full):
        raise ValueError("No evidence from verified 2021-10-19 council minutes")
    for x in full:
        if (x["representative"]!="박노학"
                or set(x["all_names"])!=EXPECTED_NAMES
                or len(x["all_names"])!=13
                or not x["every_name_unique_same_term"]
                or x["publication_status"]!="published"):
            raise ValueError("Conflicting source roster or ambiguous identity")
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    proof={
        "status":"full_roster_evidenced_not_promoted",
        "verified_full_roster":{
            "representative":"박노학",
            "all_names":full[0]["all_names"],
            "proposer_count":13,
        },
        "evidence":full,
    }
    upgraded=promote_one(row,proof,by_meeting,stamp)
    new=[upgraded if str(x["internal_number"])==ID else x for x in items]
    if any(indexed[key]!=next(x for x in new if str(x["internal_number"])==key) for key in original_institutions):
        raise ValueError("Institutional bill source data was unexpectedly modified")

    # All writes are to an isolated Actions checkout until every validation
    # succeeds; the workflow commits only after all gates pass.
    save_json(items_path,new)
    links=link(root)
    audit_result=audit(root)
    if links["proposer_rows"]!=11421 or links["unresolved"] or links["ambiguous_same_term"]:
        raise ValueError("Unexpected relationship count/identity ambiguity")
    if len(audit_result["member_bills_without_names"])!=7:
        raise ValueError("Pending incomplete rosters do not equal seven")
    if audit_result["nonmember_bill_link_rows"]!=44:
        raise ValueError("Institutional anomalies changed during independent bill correction")
    if audit_result["nonmember_bills_with_person_names"]!=5:
        raise ValueError("Institutional item source fields changed")

    repair_path=root/"reports/bill-proposer-repair.json"
    repair=read(repair_path)
    repair.update({
        "checked_at":stamp,
        "member_bills_with_names":886,
        "member_bills_without_names":7,
        "representative_rows":sum(len(x.get("representative_proposers") or []) for x in new),
        "co_proposer_rows":sum(len(x.get("co_proposers") or []) for x in new),
        "minutes_verified_member_bills_total":18,
        "minutes_verified_proposer_rows_total":263,
    })
    save_json(repair_path,repair)
    summary_path=root/"reports/bills.json"
    summary=read(summary_path)
    summary.update({
        "checked_at":stamp,
        "member_with_proposer_roster":886,
        "member_needing_minutes_fallback":7,
        "with_full_proposer_roster":sum(bool(r.get("full_proposer_names")) for r in new),
        "proposer_roster_status":"18_official_minutes_verified_7_pending",
    })
    save_json(summary_path,summary)

    validated=validate(root)
    exported=export(root)
    if exported["datasets"]["bill_proposers"]["rows"]!=11421 or exported["datasets"]["meetings"]["rows"]!=2339:
        raise ValueError("Unexpected analyzer export")
    m_audit=audit_meetings(root)
    if m_audit["status"]!="PASS":
        raise ValueError(f"Stage C source integrity failed: {m_audit['errors'][:3]}")
    result={
        "checked_at":stamp,
        "status":"PASS",
        "internal_number":ID,
        "official_bill_url":row["official_url"],
        "evidence_meeting_id":SOURCE_MEETING_ID,
        "evidence_meeting_url":official["official_url"],
        "source_meeting_content_sha256":official["content_sha256"],
        "verbatim_title":row["title"],
        "full_roster_evidence":full,
        "representative":"박노학",
        "all_proposers":upgraded["full_proposer_names"],
        "added_relationships":13,
        "total_person_relationships":11421,
        "remaining_missing_rosters":7,
        "anomalous_institutional_person_links_unchanged":44,
        "archive_validation":validated["status"],
        "meeting_integrity":m_audit["status"],
        "meeting_integrity_error_count":m_audit.get("error_count"),
        "analytical_judgments_in_archive":False,
        "main_branch_modified":False,
    }
    save_json(root/"reports/bill-1960-official-roster-promotion.json",result)
    return result

if __name__=="__main__":
    x=promote()
    print(json.dumps({k:v for k,v in x.items() if k not in ("full_roster_evidence","all_proposers")},ensure_ascii=False,indent=2))
