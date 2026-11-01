"""Export archive source facts for downstream CheongjuCouncilAnalyzer ingestion.

Exports are derived views only. Source archive files are never rewritten.
"""
from __future__ import annotations
import datetime as dt, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"exports/analyzer"

def _load(path:Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

def _write_jsonl(path:Path,rows:list[dict]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n")

def _digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def _merge(root:Path,paths:list[str])->list[dict]:
    out=[]
    for rel in paths:
        out.extend(_load(root/rel))
    return out

def export(root:Path=ROOT)->dict:
    out=root/"exports/analyzer"
    out.mkdir(parents=True,exist_ok=True)

    datasets={
        "people":_merge(root,[
            "archive/people/people.json",
            "archive/people/history/cheongju_integrated_people.json",
            "archive/people/history/cheongju_old_city_people_candidates.json",
            "archive/people/history/cheongwon_old_county_people_candidates.json",
        ]),
        "tenures":_merge(root,[
            "archive/people/tenures.json",
            "archive/people/history/cheongju_integrated_tenures.json",
            "archive/people/history/cheongju_old_city_tenures.json",
            "archive/people/history/cheongwon_old_county_tenures.json",
        ]),
        "party_memberships":_merge(root,[
            "archive/people/party_memberships.json",
        ]),
        "district_memberships":_merge(root,[
            "archive/people/district_memberships.json",
            "archive/people/history/cheongju_integrated_district_memberships.json",
        ]),
        "represented_areas":_merge(root,[
            "archive/people/history/cheongju_old_city_represented_areas.json",
            "archive/people/history/cheongwon_old_county_represented_areas.json",
        ]),
        "committee_memberships":_merge(root,[
            "archive/committees/current_memberships.json",
            "archive/committees/historical_memberships.json",
        ]),
        "committee_states":_merge(root,[
            "archive/committees/current_committees.json",
            "archive/committees/historical_states.json",
        ]),
        "research_groups":_merge(root,[
            "archive/research_groups/current_groups.json",
        ]),
        "research_group_memberships":_merge(root,[
            "archive/research_groups/current_memberships.json",
        ]),
        "bills":_merge(root,[
            "archive/bills/items.json",
        ]),
        "bill_proposers":_merge(root,[
            "archive/bills/proposer_memberships.json",
        ]),
        "meetings":_merge(root,[
            "indexes/integrated/meetings.json",
            "indexes/integrated/meeting_inventory.json",
        ]),
        "identity_candidates":_merge(root,[
            "archive/people/identity_candidates.json",
        ]),
    }

    # Avoid double-exporting meeting inventory if full meeting index exists.
    full=root/"indexes/integrated/meetings.json"
    if full.exists():
        datasets["meetings"]=_load(full)

    manifest={
        "schema":"cheongju-council-archive-analyzer-export/0.1",
        "generated_at":dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(),
        "datasets":{},
        "principles":{
            "source_facts_only":True,
            "analysis_judgments_included":False,
            "identity_candidates_non_promoting":True,
        },
    }
    for name,rows in datasets.items():
        path=out/f"{name}.jsonl"
        _write_jsonl(path,rows)
        manifest["datasets"][name]={
            "rows":len(rows),
            "path":str(path.relative_to(root)).replace("\\","/"),
            "sha256":_digest(path),
        }

    mpath=out/"manifest.json"
    mpath.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest

if __name__=="__main__":
    print(json.dumps(export(),ensure_ascii=False,indent=2))
