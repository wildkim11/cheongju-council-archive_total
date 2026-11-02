"""Entire-archive disposable rehearsal: SYNTHETIC provisional-to-published and body drift.

This deliberately invents a future change to existing IDs 4019 and 3999.
These changes DO NOT EXIST as confirmed source facts and must NEVER be exported
to the actual Cheongju City Council archive. No official website requests.
Real 2,339-source Markdown bytes are copied to a temporary root; revision
history, published/provisional indexes, regenerated analyzer and all hashes
are audited there only. The ROOT production collector interlock stays locked.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import audit_stage_c
import collect_integrated_minutes as c

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/"reports/synthetic-status-and-published-body-drift-2339-full-copy-20261102.json"
PROVISIONAL_TO_PUBLISHED = "4019"
PUBLISHED_BODY_DRIFT = "3999"
REMOVE_FIELDS = (
    "path","content_sha256","sha256","bytes",
    "first_seen_at","last_checked_at","supersedes","superseded_by",
)


def load(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path:Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    saved=load(ROOT/"indexes/integrated/meetings.json")
    if len(saved)!=2339:
        raise RuntimeError("Expected exact original 2339-source baseline")
    prior={str(row["source_id"]):row for row in saved}
    if (prior[PROVISIONAL_TO_PUBLISHED]["publication_status"]!="provisional"
        or prior[PUBLISHED_BODY_DRIFT]["publication_status"]!="published"):
        raise RuntimeError("Original source status changed; do not silently choose another ID")
    initial_hashes={sid:row["sha256"] for sid,row in prior.items()}
    actual_root_index_hash=digest(ROOT/"indexes/integrated/meetings.json")
    actual_root_export_hash=digest(ROOT/"exports/analyzer/meetings.jsonl")

    with tempfile.TemporaryDirectory(prefix="cheongju-synthetic-transition-body-drift-") as td:
        copy=Path(td)/"full-copy"
        copy.mkdir()
        for name in ("archive","indexes","reports","exports"):
            shutil.copytree(ROOT/name,copy/name)
        before=audit_stage_c.audit(copy)
        if before["status"]!="PASS":
            raise RuntimeError("Failed baseline full-copy audit")
        live=[{k:v for k,v in row.items() if k not in REMOVE_FIELDS} for row in saved]
        for row in live:
            if row["source_id"]==PROVISIONAL_TO_PUBLISHED:
                row["publication_status"]="published"
        live.sort(key=lambda r:(r["date"],r["meeting_id"]))
        bodies={}
        for source in saved:
            sid=source["source_id"]
            if source["publication_status"]=="provisional" or sid==PUBLISHED_BODY_DRIFT:
                text=(copy/source["path"]).read_text(encoding="utf-8")
                _,_,body=audit_stage_c.markdown_parts(text)
                if sid==PUBLISHED_BODY_DRIFT:
                    body+="\n\n[오프라인 합성 본문 수정 시험용 문구 — 실제 청주시의회 변경 사실 아님]"
                bodies[sid]=body
        if len(bodies)!=7:
            raise AssertionError("Expected six provisional source bodies plus published drift")
        calls=[]
        def fake_fetch(url):
            sid=url.rsplit("schSn=",1)[-1]
            if sid not in bodies:
                raise AssertionError("Unexpected source requested: "+sid)
            calls.append(sid)
            return sid
        previous_inventory_qa=load(ROOT/"reports/integrated-sync.json")["inventory_qa"]
        with patch.object(c,"read_official_inventory",return_value=(live,previous_inventory_qa)), \
             patch.object(c,"fetch",side_effect=fake_fetch), \
             patch.object(c,"extract_minutes_body",side_effect=lambda sid:bodies[sid]):
            result=c.run_sync(
                "incremental",copy,
                force_body_ids={f"cheongju_integrated:minutes-{PUBLISHED_BODY_DRIFT}"},
            )
        updated=load(copy/"indexes/integrated/meetings.json")
        after=audit_stage_c.audit(copy)
        by_id={str(row["source_id"]):row for row in updated}
        if len(updated)!=2339 or after["status"]!="PASS":
            raise AssertionError("Isolated complete audit or total count failed")
        unchanged=sum(
            row["sha256"]==by_id[sid]["sha256"]
            and digest(copy/row["path"])==row["sha256"]
            for sid,row in prior.items()
            if sid not in {PROVISIONAL_TO_PUBLISHED,PUBLISHED_BODY_DRIFT}
        )
        revisions=load(copy/"indexes/integrated/meeting_revisions.json")
        by_revision={row["source_id"]:row for row in revisions}
        if len(revisions)!=2 or set(by_revision)!={PROVISIONAL_TO_PUBLISHED,PUBLISHED_BODY_DRIFT}:
            raise AssertionError("Expected two source-preserving immutable revision records")
        original_revisions={
            sid:(copy/by_revision[sid]["revision_path"]).read_bytes()==(ROOT/prior[sid]["path"]).read_bytes()
            for sid in by_revision
        }
        export=load(copy/"exports/analyzer/manifest.json")
        valid=all((
            unchanged==2337,
            all(original_revisions.values()),
            by_id[PROVISIONAL_TO_PUBLISHED]["publication_status"]=="published",
            by_id[PUBLISHED_BODY_DRIFT]["content_sha256"]!=prior[PUBLISHED_BODY_DRIFT]["content_sha256"],
            after["source_rows"]==2339,
            after["sha256_file_verified"]==2339,
            after["sha256_content_verified"]==2339,
            after["revisions_verified"]==2,
            after["published"]==2334,
            after["provisional"]==5,
            after["export_rows_checked"]==2339,
            export["datasets"]["meetings"]["rows"]==2339,
            result["forced_body_checks"]==[f"cheongju_integrated:minutes-{PUBLISHED_BODY_DRIFT}"],
            len(calls)==7,
        ))
        report={
            "schema":"synthetic-published-body-and-provisional-transition-full-copy/1",
            "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "status":"PASS" if valid else "FAIL",
            "data_type":"ENTIRELY_SYNTHETIC_CHANGES_TO_EXISTING_SAVED_BODIES",
            "actual_official_site_requests":0,
            "offline_full_original_copy_source_count":2339,
            "simulated_provisional_to_published_id":PROVISIONAL_TO_PUBLISHED,
            "simulated_published_same_id_body_drift_id":PUBLISHED_BODY_DRIFT,
            "force_published_body_recheck_exercised":result["forced_body_checks"],
            "changed_originals":sorted([PROVISIONAL_TO_PUBLISHED,PUBLISHED_BODY_DRIFT]),
            "unchanged_other_originals":unchanged,
            "old_versions_immutably_preserved":original_revisions,
            "revision_ledger_entries":len(revisions),
            "current_meetings":after["source_rows"],
            "current_published":after["published"],
            "current_provisional":after["provisional"],
            "sha256_files_verified":after["sha256_file_verified"],
            "sha256_bodies_verified":after["sha256_content_verified"],
            "analyzer_export_meeting_rows":after["export_rows_checked"],
            "analyzer_export_file_hashes_verified":after["export_files_hash_verified"],
            "stage_c_audit":after["status"],
            "stage_c_errors":after["errors"][:8],
            "production_root_unchanged":True,
            "production_sync_hard_lock_kept":True,
            "no_schedule_enabled":True,
            "no_real_source_claims_from_synthetic_data":True,
        }
        if not valid:
            raise RuntimeError(json.dumps(report,ensure_ascii=False,indent=2))
    # The disposable modified index/export and all versions are now gone.
    if (digest(ROOT/"indexes/integrated/meetings.json")!=actual_root_index_hash
        or digest(ROOT/"exports/analyzer/meetings.jsonl")!=actual_root_export_hash):
        raise RuntimeError("ORIGINAL_PROJECT_INDEX_OR_ANALYZER_CHANGED")
    if audit_stage_c.audit(ROOT)["status"]!="PASS":
        raise RuntimeError("ORIGINAL_PROJECT_ARCHIVE_FAILED_AFTER_SYNTHETIC_TEST")
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=="__main__":
    run()
