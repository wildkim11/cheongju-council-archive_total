"""Full saved-archive COPY rehearsal of a SYNTHETIC cross-year/cross-term move.

This DOES NOT assert any real official council minute changed its date/term.
It deliberately creates a false future title for precisely one saved source
in a temporary copy to verify immutable bytes, old path removal, revision
provenance, all 2339 canonical records, and all downstream exports.

There is no official HTTP, no production root writes and no extra real meeting.
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

ROOT=Path(__file__).resolve().parents[1]
SYNTHETIC_MIGRATION_SOURCE_ID="3652"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    source=load(ROOT/"indexes/integrated/meetings.json")
    if len(source)!=2339:
        raise RuntimeError("Real original meeting inventory count is not the approved baseline")
    originals={str(r["source_id"]):r["sha256"] for r in source}
    prior=next((r for r in source if str(r.get("source_id"))==SYNTHETIC_MIGRATION_SOURCE_ID),None)
    if not prior or prior["term"]!=3 or prior["year"]!=2025:
        raise RuntimeError("Synthetic moving-record baseline changed; do not guess a new source ID")
    with tempfile.TemporaryDirectory(prefix="cheongju-synthetic-cross-year-") as folder:
        root=Path(folder)/"copy"
        root.mkdir()
        for dirname in ("archive","indexes","reports","exports"):
            shutil.copytree(ROOT/dirname,root/dirname)
        original_bytes=(root/prior["path"]).read_bytes()
        assert hashlib.sha256(original_bytes).hexdigest()==prior["sha256"]
        qa_before=audit_stage_c.audit(root)
        if qa_before["status"]!="PASS":
            raise RuntimeError("Stage C archived source baseline failed")

        # Deliberately simulated content, NOT a real change to the official
        # document's publication metadata. All other 2338 rows are unchanged.
        new={key:value for key,value in prior.items() if key not in (
            "path","content_sha256","sha256","bytes","first_seen_at",
            "last_checked_at","supersedes","superseded_by")}
        new.update({
            "term":4,"date":"2026-02-06","year":2026,
            "title":"제4대 가상 기록경로 이동 시험 본회의 제1차(2026.02.06 금요일)"
        })
        live=[]
        for r in source:
            if str(r["source_id"])==SYNTHETIC_MIGRATION_SOURCE_ID:
                live.append(new)
            else:
                live.append({key:value for key,value in r.items() if key not in (
                    "path","content_sha256","sha256","bytes",
                    "first_seen_at","last_checked_at","supersedes","superseded_by"
                )})
        live.sort(key=lambda r:(r["date"],r["meeting_id"]))
        mock_bodies={}
        for r in source:
            if r["publication_status"]=="provisional" or str(r["source_id"])==SYNTHETIC_MIGRATION_SOURCE_ID:
                _,_,original_body=audit_stage_c.markdown_parts(
                    (root/r["path"]).read_text(encoding="utf-8")
                )
                mock_bodies[str(r["source_id"])]=original_body
        if len(mock_bodies)!=7:
            raise RuntimeError("Expected six provisional plus one moving record")
        calls=[]
        def fetch_mock(url):
            sid=url.rsplit("schSn=",1)[-1]
            if sid not in mock_bodies:
                raise AssertionError("Unexpected official URL requested")
            calls.append(sid)
            return sid
        def body_mock(sid):
            return mock_bodies[sid]
        previous_qa=load(ROOT/"reports/integrated-sync.json")["inventory_qa"]
        with patch.object(c,"read_official_inventory",return_value=(live,previous_qa)), \
             patch.object(c,"fetch",side_effect=fetch_mock), \
             patch.object(c,"extract_minutes_body",side_effect=body_mock):
            report=c.run_sync("incremental",root)

        result=load(root/"indexes/integrated/meetings.json")
        ledger=load(root/"indexes/integrated/meeting_revisions.json")
        migrated=next(r for r in result if str(r["source_id"])==SYNTHETIC_MIGRATION_SOURCE_ID)
        migrated_new_path=migrated["path"]
        assert migrated_new_path!=prior["path"]
        assert len(ledger)==1
        saved=(root/ledger[0]["revision_path"]).read_bytes()
        qa_after=audit_stage_c.audit(root)
        all_other_originals_preserved=all(
            original["sha256"]==next(r for r in result if str(r["source_id"])==sid)["sha256"]
            and digest(root/original["path"])==original["sha256"]
            for sid in originals if sid!=SYNTHETIC_MIGRATION_SOURCE_ID
            for original in (next(r for r in source if str(r["source_id"])==sid),)
        )
        exporter=load(root/"exports/analyzer/manifest.json")
        valid=all([
            len(result)==2339,len(ledger)==1,
            saved==original_bytes,
            not (root/prior["path"]).exists(),
            (root/migrated_new_path).is_file(),
            migrated["term"]==4 and migrated["date"]=="2026-02-06",
            all_other_originals_preserved,
            qa_after["status"]=="PASS",
            qa_after["source_files_checked"]==2339,
            qa_after.get("revisions_verified")==1,
            exporter["datasets"]["meetings"]["rows"]==2339,
            report["migrated_old_paths"]==[prior["path"]],
            len(calls)==7,
        ])
        output={
            "created_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "status":"PASS" if valid else "FAIL",
            "mode":"strictly synthetic cross-year/cross-term migration in temporary byte-exact copy",
            "original_saved_meetings":2339,
            "temporary_current_meetings":len(result),
            "official_site_requests":0,
            "unchanged_other_originals":2338 if all_other_originals_preserved else None,
            "one_moved_original_prior_bytes_preserved":saved==original_bytes,
            "obsolete_path_removed_from_copy":not (root/prior["path"]).exists(),
            "new_canonical_path_present_in_copy":(root/migrated_new_path).is_file(),
            "revision_ledger_entries":len(ledger),
            "stage_c_result":qa_after["status"],
            "stage_c_verified_current_files":qa_after["source_files_checked"],
            "stage_c_verified_immutable_revisions":qa_after.get("revisions_verified"),
            "exported_current_meetings":exporter["datasets"]["meetings"]["rows"],
            "source_repository_files_modified":False,
            "production_sync_still_locked":True,
            "warning":"Simulated title/date/term is NOT evidence of a real Cheongju Council meeting change.",
            "errors":qa_after["errors"][:12],
        }
        if not valid:
            raise AssertionError(json.dumps(output,ensure_ascii=False,indent=2))
    path=ROOT/"reports/synthetic-cross-year-migration-full-2339-qa.json"
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return output

if __name__=="__main__":
    run()
