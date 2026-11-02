"""Read-only reconciliation of Stage A 434 vs 435 source-person rows.

Each archived profile row is not necessarily a deduplicated natural person.
Do not auto-merge same-name candidate identities across distinct council scopes.
"""
from __future__ import annotations
import collections
import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARTS=[
    ("current_4th_term","archive/people/people.json","archive/people/tenures.json",44),
    ("integrated_terms_1_3","archive/people/history/cheongju_integrated_people.json",
     "archive/people/history/cheongju_integrated_tenures.json",123),
    ("pre_merger_cheongju","archive/people/history/cheongju_old_city_people_candidates.json",
     "archive/people/history/cheongju_old_city_tenures.json",187),
    ("pre_merger_cheongwon","archive/people/history/cheongwon_old_county_people_candidates.json",
     "archive/people/history/cheongwon_old_county_tenures.json",80),
    ("integrated_term4_historical_only","archive/people/history/cheongju_integrated_term4_departed_people.json",
     "archive/people/history/cheongju_integrated_term4_departed_tenures.json",1),
]

def load(root,relative):
    return json.loads((root/relative).read_text(encoding="utf-8"))

def audit(root=ROOT):
    entries=[]
    identities=[]
    for label,people_path,tenure_path,expected in PARTS:
        people=load(root,people_path)
        tenures=load(root,tenure_path)
        if len(people)!=expected or len(tenures)!=expected:
            raise ValueError(f"Expected {expected} source rows from {label}, got people={len(people)}, tenures={len(tenures)}")
        pids={p["person_id"] for p in people}
        tids={t["person_id"] for t in tenures}
        if len(pids)!=expected or tids!=pids:
            raise ValueError(f"People/tenure source IDs do not match within {label}")
        identities.extend(p["person_id"] for p in people)
        entries.append({
            "category":label,
            "people_file":people_path,
            "tenure_file":tenure_path,
            "people_records":len(people),
            "tenure_records":len(tenures),
        })
    if len(identities)!=435 or len(set(identities))!=435:
        raise ValueError("Expected 435 unique SOURCE person IDs, not natural-person identities")
    historical=load(root,PARTS[-1][1])
    t4=load(root,PARTS[-1][2])
    p=historical[0]
    if not (p["name"]=="최영중"
            and p["official_profile_code"]=="4200"
            and p["identity_status"]=="candidate_unmerged"
            and p.get("historical_only_current_term") is True):
        raise ValueError("The official current-term historical-only row has changed")
    if t4[0].get("term")!=4 or t4[0].get("council_scope")!="cheongju_integrated":
        raise ValueError("Extra person not proven as same-scope term 4 historical tenure")
    reports={
        "current":load(root,"reports/current-members.json")["current_members"],
        "integrated":load(root,"reports/cheongju_integrated-historical-members.json")["roster_rows"],
        "old_city":load(root,"reports/cheongju_old_city-historical-members.json")["people_candidate_rows"],
        "old_county":load(root,"reports/cheongwon_old_county-historical-members.json")["people_candidate_rows"],
        "historical_only":load(root,"reports/cheongju_integrated-term4-historical-only.json")["historical_only_rows"],
    }
    if list(reports.values())!=[44,123,187,80,1]:
        raise ValueError(f"Source report count conflict: {reports}")
    manifest=load(root,"exports/analyzer/manifest.json")
    if manifest["datasets"]["people"]["rows"]!=435 or manifest["datasets"]["tenures"]["rows"]!=435:
        raise ValueError("Analyzer people/tenures export count conflicts with canonical archive")
    return {
        "checked_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "status":"PASS",
        "archived_profile_records":435,
        "archived_tenure_records":435,
        "previous_baseline_excluding_historical_only":434,
        "extra_historical_only":1,
        "breakdown":entries,
        "single_added_record":{
            "name":p["name"],"person_id":p["person_id"],
            "council_scope":t4[0]["council_scope"],"term":t4[0]["term"],
            "official_profile_url":p["official_profile_url"],
            "official_profile_code":p["official_profile_code"],
            "source_url":p["source_url"],
            "identity_status":p["identity_status"],
            "recorded_start_date":t4[0].get("start_date"),
            "recorded_end_date":t4[0].get("end_date"),
        },
        "source_counts_match":True,
        "analyzer_manifest_people_and_tenures_match":True,
        "meaning":"435 source records, NOT 435 verified distinct natural persons",
        "archive_data_modified":False,
    }

if __name__=="__main__":
    result=audit()
    path=ROOT/"reports/stage-a-people-count-reconciliation.json"
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
