"""Archive-level invariants independent of source-site availability."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCOPES={"cheongju_integrated","cheongju_old_city","cheongwon_old_county"}
PUBLICATION={"provisional","published","superseded"}
FORBIDDEN_ANALYSIS_FIELDS={
    "q_code","q_type","event_id","event_score","p_stage","policy_interest",
    "ranking","rank","score","probability","prediction"
}

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def _walk(obj):
    if isinstance(obj,dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj,list):
        for v in obj:
            yield from _walk(v)

def _check_no_analysis_fields(obj, errors, source):
    for node in _walk(obj):
        bad=FORBIDDEN_ANALYSIS_FIELDS.intersection(node)
        if bad:
            errors.append(f"{source}: downstream-only fields present: {sorted(bad)}")

def validate(root: Path=ROOT):
    errors=[]
    warnings=[]

    people_files=[
        root/"archive/people/people.json",
        root/"archive/people/history/cheongju_integrated_people.json",
        root/"archive/people/history/cheongju_integrated_term4_departed_people.json",
        root/"archive/people/history/cheongju_old_city_people_candidates.json",
        root/"archive/people/history/cheongwon_old_county_people_candidates.json",
    ]
    people=[]
    for people_path in people_files:
        if not people_path.exists():
            continue
        rows=load_json(people_path)
        people.extend(rows)
        for p in rows:
            if not p.get("person_id") or not p.get("name"):
                errors.append(f"{people_path}: person missing person_id/name")
            portrait=p.get("portrait")
            if portrait and portrait.get("local_path"):
                if not portrait.get("source_url") or not portrait.get("sha256"):
                    errors.append(f"{p.get('person_id')}: incomplete portrait provenance")
        _check_no_analysis_fields(rows,errors,str(people_path))

    ids=[p.get("person_id") for p in people]
    if len(ids)!=len(set(ids)):
        errors.append("duplicate person_id across people ledgers")
    known_person_ids=set(ids)

    meetings_path=root/"indexes/integrated/meetings.json"
    if meetings_path.exists():
        meetings=load_json(meetings_path)
        ids=[m.get("meeting_id") for m in meetings]
        if len(ids)!=len(set(ids)):
            errors.append("duplicate meeting_id")
        for m in meetings:
            if m.get("council_scope") not in SCOPES:
                errors.append(f"{m.get('meeting_id')}: invalid council_scope")
            if m.get("publication_status") not in PUBLICATION:
                errors.append(f"{m.get('meeting_id')}: invalid publication_status")
            if m.get("publication_status")=="superseded" and not m.get("superseded_by"):
                warnings.append(f"{m.get('meeting_id')}: superseded without successor link")
        _check_no_analysis_fields(meetings,errors,str(meetings_path))

    for name in [
        "tenures.json","party_memberships.json","district_memberships.json",
        "committee_memberships.json"
    ]:
        path=root/"archive/people"/name
        if not path.exists(): continue
        rows=load_json(path)
        for row in rows:
            if row.get("council_scope") not in SCOPES:
                errors.append(f"{path}: invalid council_scope")
            if not isinstance(row.get("term"),int) or row["term"]<1:
                errors.append(f"{path}: invalid term")
            if not row.get("source_url"):
                errors.append(f"{path}: missing source_url")
        _check_no_analysis_fields(rows,errors,str(path))

    # Referential integrity: any promoted relationship/activity identity link
    # that carries a person_id must reference a person present in the archive.
    reference_paths=[
        root/"archive/committees/current_memberships.json",
        root/"archive/committees/historical_memberships.json",
        root/"archive/research_groups/current_memberships.json",
        root/"archive/research_groups/historical_memberships.json",
        root/"archive/bills/proposer_memberships.json",
    ]
    for path in reference_paths:
        if not path.exists():
            continue
        rows=load_json(path)
        for row in rows:
            pid=row.get("person_id")
            if pid and pid not in known_person_ids:
                errors.append(f"{path}: dangling person_id {pid}")
        _check_no_analysis_fields(rows,errors,str(path))

    if errors:
        raise SystemExit("ARCHIVE VALIDATION FAILED\n- "+"\n- ".join(errors))
    return {"status":"PASS","warnings":warnings}

if __name__=="__main__":
    print(json.dumps(validate(),ensure_ascii=False,indent=2))
