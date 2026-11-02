"""Real official two-new-meeting full-copy incremental rehearsal, never production.

Read ONLY schSn=4024,4025 on GitHub macOS with the original TLS configuration.
Verify canonical body hashes against prior live read-only evidence.
A disposable byte-exact 2339-source COPY receives an isolated incremental sync
to 2341; six old provisional original bodies are replayed from checksum-verified
saved files, without any old-site requests. Test all source/index/export hashes.

On a SECOND disposable baseline copy, simulate SIGKILL during WAL installation,
recover the interrupted transaction and verify exact original index/exports and
source files. Never mutate this repo's canonical archive, its main branch,
the live sync hard-interlock, or any scheduled jobs.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_stage_c
import collect_integrated_minutes as c
import probe_official_new_term4_bodies_macos as viewer
import sync_transaction

OUT = ROOT / "reports/official-real-two-new-2341-full-copy-rehearsal-20261102.json"
INDEX = ROOT / "indexes/integrated/meetings.json"
DISCOVERY = ROOT / "reports/official-term4-new-meeting-id-discovery-20261102.json"
YEAR = ROOT / "reports/official-year2026-new-ids-presence-20261102.json"
PREVIOUS_BODY = ROOT / "reports/official-term4-new-meeting-body-check-20261102.json"
EXPECTED = ("4024", "4025")
NEW_BODY_SHA = {
    "4024": "818fa74efdb62b563d5ba4ce8c23a47e5c9811113e0b3e493f82fe3ee5b6545d",
    "4025": "56a6503293a26f9cec67d6170dfaa5fa93b0047cacbb5438c55fd192592f3eba",
}
STRIP = {
    "path", "content_sha256", "sha256", "bytes",
    "first_seen_at", "last_checked_at", "supersedes", "superseded_by",
}
COPY_DIRS = ("archive", "indexes", "reports", "exports")
BASELINE = 2339
BASELINE_TERM4 = 50


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in STRIP}


def build_verified_fixture(saved: list[dict]) -> tuple[list[dict], dict, dict]:
    """Only source-derived official evidence may supply new records."""
    discovery = load(DISCOVERY)
    year = load(YEAR)
    prior_body = load(PREVIOUS_BODY)
    if len(saved) != BASELINE or sum(x["term"] == 4 for x in saved) != BASELINE_TERM4:
        raise ValueError("EXPECTED_2339_BASELINE_AND_50_TERM4")
    if (
        not discovery.get("official_term4_coverage_complete")
        or discovery.get("branch_errors")
        or discovery.get("observed_term4_official_unique_ids") != 52
        or discovery.get("saved_term4_count") != 50
        or discovery.get("status_change_candidates")
        or discovery.get("metadata_change_candidates")
        or discovery.get("missing_saved_term4_ids_full_branch_only")
    ):
        raise ValueError("OFFICIAL_TERM4_INVENTORY_NOT_STABLE_AND_COMPLETE")
    candidate_list = discovery.get("new_source_id_candidates", [])
    if {str(x["source_id"]) for x in candidate_list} != set(EXPECTED) or len(candidate_list) != 2:
        raise ValueError("UNEXPECTED_NEW_OFFICIAL_SOURCE_ID_SET")
    if (
        year.get("status") != "PASS_BOTH_NEW_IDS_IN_OFFICIAL_YEAR2026"
        or set(year.get("found", {})) != set(EXPECTED)
        or any(year["found"][sid]["official_status_code"] != "N" for sid in EXPECTED)
    ):
        raise ValueError("YEAR_2026_SOURCE_MEMBERSHIP_NOT_VERIFIED")
    prior = {str(x["source_id"]): x for x in prior_body.get("responses", [])}
    if (
        prior_body.get("decision") != "BOTH_NEW_OFFICIAL_BODIES_READABLE_READY_FOR_ISOLATED_IMPORT_REHEARSAL"
        or set(prior) != set(EXPECTED)
        or any(prior[sid].get("body_normalized_sha256") != NEW_BODY_SHA[sid] for sid in EXPECTED)
    ):
        raise ValueError("PRIOR_NEW_BODY_HASH_BASELINE_MISMATCH")

    old_ids = {str(row["source_id"]) for row in saved}
    if len(old_ids) != BASELINE or old_ids.intersection(EXPECTED):
        raise ValueError("EXISTING_SOURCE_ID_COLLISION")
    added = {}
    for row in candidate_list:
        sid = str(row["source_id"])
        if (row.get("official_session") != "106"
            or row.get("official_status") != "provisional"
            or row.get("official_url") != (
                "https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/"
                f"SvcMntsViewer.php?schSn={sid}"
            )):
            raise ValueError("UNVERIFIED_NEW_MEETING_OFFICIAL_METADATA")
        date = str(row["official_date"])
        dt.date.fromisoformat(date)
        title = str(row["official_title"])
        committee = str(row["official_committee_code"])
        added[sid] = {
            "meeting_id": f"cheongju_integrated:minutes-{sid}",
            "legacy_minutes_id": f"minutes-{sid}",
            "council_scope": "cheongju_integrated",
            "term": 4,
            "title": title,
            "date": date,
            "year": int(date[:4]),
            "committee_code": committee,
            "meeting_type": c._meeting_type(title, committee),
            "publication_status": "provisional",
            "official_url": row["official_url"],
            "source_id": sid,
            "inventory_sources": ["term", "year"],
        }
    rows = [metadata(row) for row in saved] + list(added.values())
    rows.sort(key=lambda row: (row["date"], row["meeting_id"]))
    old_qa = load(ROOT / "reports/integrated-sync.json")["inventory_qa"]
    term_only = sorted(
        (str(row["source_id"]) for row in rows if row["inventory_sources"] == ["term"]),
        key=int,
    )
    if set(term_only) != set(old_qa["only_term"]) or old_qa["only_year"]:
        raise RuntimeError("ORIGINAL_YEAR_TERM_13_EXCEPTION_LIST_CHANGED")
    inventory_qa = {
        **old_qa,
        "term_inventory_count": len(rows),
        "year_inventory_count": len(rows) - len(term_only),
        "shared_count": len(rows) - len(term_only),
        "only_term": term_only,
        "only_year": [],
    }
    if len(rows) != 2341 or inventory_qa["year_inventory_count"] != 2328:
        raise AssertionError("UNEXPECTED_2341_INVENTORY_FIXTURE_COUNTS")
    return rows, added, inventory_qa


def copy_snapshot(target: Path):
    target.mkdir(parents=True, exist_ok=False)
    for item in COPY_DIRS:
        shutil.copytree(ROOT / item, target / item)


def verify_original_bytes(target: Path, rows: list[dict]) -> int:
    count = 0
    for row in rows:
        source = target / row["path"]
        if not source.is_file() or digest(source) != row["sha256"]:
            raise AssertionError("ORIGINAL_SOURCE_HASH_CHANGED: " + str(row["source_id"]))
        count += 1
    if count != BASELINE:
        raise AssertionError("SOURCE_COUNT_CHANGED")
    return count


def official_two_bodies() -> tuple[dict[str,str],dict]:
    bodies = {}
    response_meta = []
    for sid in EXPECTED:
        status, raw = viewer.get_viewer(sid)  # one HTTPS GET per new ID, no retries
        if status != 200:
            raise RuntimeError("NEW_OFFICIAL_MEETING_NON_200: " + sid)
        body = c.extract_minutes_body(raw.decode("utf-8-sig"))
        source_sha = hashlib.sha256(c.canonical(body).encode("utf-8")).hexdigest()
        if source_sha != NEW_BODY_SHA[sid]:
            raise RuntimeError("LIVE_NEW_BODY_CHANGED_SINCE_PRIOR_PROBE: " + sid)
        if "임시회의록" not in body:
            raise RuntimeError("NEW_SOURCE_PROVISIONAL_NOTICE_MISSING: " + sid)
        bodies[sid] = body
        response_meta.append({
            "source_id": sid, "http_status": status,
            "body_normalized_sha256": source_sha,
            "raw_response_bytes": len(raw), "body_characters": len(body),
        })
    return bodies, {
        "official_get_requests": len(response_meta),
        "official_get_retries": 0,
        "responses": response_meta,
        "body_hashes_match_previous_probe": True,
    }


def run_incremental_on_copy(root: Path, source: list[dict],
                            live_rows: list[dict], qa: dict,
                            fresh_bodies: dict[str,str]) -> tuple[dict,list[str]]:
    # Six saved provisional texts are replayed from local SHA-checked bytes.
    replay={}
    for row in source:
        if row["publication_status"] == "provisional":
            md = (root / row["path"]).read_text(encoding="utf-8")
            _, _, body = audit_stage_c.markdown_parts(md)
            value = hashlib.sha256(c.canonical(body).encode("utf-8")).hexdigest()
            if value != row["content_sha256"]:
                raise RuntimeError("SAVED_PROVISIONAL_BODY_HASH_FAILURE: "+str(row["source_id"]))
            replay[str(row["source_id"])] = body
    if len(replay) != 6:
        raise RuntimeError("EXPECTED_6_SAVED_PROVISIONAL_BODY_REPLAYS")
    all_bodies={**replay, **fresh_bodies}
    used=[]
    def local_fetch(url: str):
        sid=url.rsplit("schSn=",1)[-1]
        if sid not in all_bodies:
            raise AssertionError("UNAUTHORIZED_OFFICIAL_BODY_FETCH_MOCK: " + sid)
        used.append(sid)
        return sid
    def local_parse(token: str):
        return all_bodies[token]
    with patch.object(c, "read_official_inventory", return_value=(live_rows,qa)), \
         patch.object(c, "fetch", side_effect=local_fetch), \
         patch.object(c, "extract_minutes_body", side_effect=local_parse):
        report = c.run_sync("incremental", root)
    if sorted(used,key=int) != sorted(all_bodies,key=int):
        raise AssertionError("UNEXPECTED_INCREMENTAL_BODY_SELECTION")
    return report, sorted(used,key=int)


def sigkill_and_recover(root: Path, updated: Path, source: list[dict]) -> dict:
    """Crash a child after installing 2 WAL files; recover on a second COPY."""
    # Four+ staged changes, including new originals, canonical index and exports.
    files = [
        "archive/meetings/cheongju_integrated/term-4/2026/minutes-4024.md",
        "archive/meetings/cheongju_integrated/term-4/2026/minutes-4025.md",
        "indexes/integrated/meetings.json",
        "indexes/integrated/current_term_4.json",
        "reports/integrated-sync.json",
        "exports/analyzer/meetings.jsonl",
        "exports/analyzer/manifest.json",
    ]
    stage = root.parent / "crash-stage"
    stage.mkdir(parents=True,exist_ok=False)
    for rel in files:
        target=stage/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(updated/rel,target)
    pre_index=digest(root/"indexes/integrated/meetings.json")
    pre_export=digest(root/"exports/analyzer/meetings.jsonl")
    pre_manifest=digest(root/"exports/analyzer/manifest.json")

    script = (
        "import os,signal,sys,pathlib,sync_transaction as t\n"
        "stage=pathlib.Path(sys.argv[1]); target=pathlib.Path(sys.argv[2])\n"
        "def stop(phase,index):\n"
        "    if phase=='installed' and index==2: os.kill(os.getpid(),signal.SIGKILL)\n"
        "with t.exclusive_lock(target):\n"
        "    t.publish_staged_snapshot(stage,target,on_phase=stop)\n"
        "raise AssertionError('SIGKILL_NOT_TRIGGERED')\n"
    )
    environment=dict(os.environ)
    environment["PYTHONPATH"]=str(ROOT/"scripts")
    child=subprocess.run(
        [sys.executable,"-c",script,str(stage),str(root)],
        cwd=str(ROOT),env=environment,capture_output=True,text=True,timeout=90,
    )
    if child.returncode != -signal.SIGKILL:
        raise RuntimeError(
            "WAL_CHILD_DID_NOT_DIE_AT_EXPECTED_STEP: "
            +repr({"returncode":child.returncode,"stderr":child.stderr[-700:]})
        )
    journal=root/sync_transaction.JOURNAL
    if not journal.is_dir():
        raise RuntimeError("EXPECTED_PENDING_CRASH_JOURNAL_MISSING")
    with sync_transaction.exclusive_lock(root):
        outcome=sync_transaction.recover_pending(root)
    if journal.exists():
        raise RuntimeError("CRASH_JOURNAL_NOT_FULLY_RECOVERED")
    original_files=verify_original_bytes(root,source)
    if (digest(root/"indexes/integrated/meetings.json")!=pre_index
        or digest(root/"exports/analyzer/meetings.jsonl")!=pre_export
        or digest(root/"exports/analyzer/manifest.json")!=pre_manifest):
        raise RuntimeError("WAL_RECOVERY_DID_NOT_RESTORE_OLD_INDEX_AND_EXPORT_BYTES")
    qa=audit_stage_c.audit(root)
    if qa["status"]!="PASS" or qa["source_rows"] != BASELINE:
        raise RuntimeError("WAL_RECOVERY_BASELINE_QA_FAILED: "+repr(qa["errors"][:4]))
    return {
        "signal":"SIGKILL",
        "interrupted_after_installs":2,
        "recovery_completed":True,
        "recovery_diagnostic":outcome,
        "prior_canonical_index_exactly_restored":True,
        "prior_analyzer_meetings_and_manifest_exactly_restored":True,
        "prior_original_source_file_hashes_restored":original_files,
        "recovered_stage_c":"PASS",
        "recovered_source_count":qa["source_rows"],
    }


def run() -> dict:
    if platform.system() != "Darwin":
        raise RuntimeError("MACOS_LIVE_REHEARSAL_ONLY")
    if not ROOT.is_dir() or not INDEX.is_file():
        raise RuntimeError("REPOSITORY_BASELINE_REQUIRED")
    source=load(INDEX)
    rows,added,inventory_qa=build_verified_fixture(source)
    baseline_qa=audit_stage_c.audit(ROOT)
    if baseline_qa["status"] != "PASS" or baseline_qa["source_rows"]!=BASELINE:
        raise RuntimeError("EXISTING_ORIGINAL_BASELINE_AUDIT_FAILED")
    original_index_hash=digest(INDEX)
    original_export_hash=digest(ROOT/"exports/analyzer/meetings.jsonl")
    original_manifest_hash=digest(ROOT/"exports/analyzer/manifest.json")

    # Exactly two real official requests; abort before making a COPY if body drift.
    fresh_bodies,official_check=official_two_bodies()
    result={
        "schema":"official-real-two-new-full-copy-incremental-rehearsal/1",
        "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"real 4024 and 4025 official bodies; disposable full 2339-source snapshot; isolated incremental",
        "live_official":official_check,
        "original_source_count":BASELINE,
        "expected_copy_source_count":2341,
        "original_root_never_used_for_incremental":True,
        "archive_root_modified":False,
        "main_branch_modified":False,
        "production_sync_hard_lock_maintained":True,
        "scheduled_collection_enabled":False,
        "operational_release_authorized":False,
        "status":"IN_PROGRESS",
    }
    with tempfile.TemporaryDirectory(prefix="cheongju-real-two-new-2341-") as temp:
        temp_root=Path(temp)
        working=temp_root/"working-copy"
        copied_before_crash=temp_root/"crash-copy"
        copy_snapshot(working)
        copy_snapshot(copied_before_crash)
        if verify_original_bytes(working,source)!=BASELINE:
            raise RuntimeError("FAILED_SOURCE_COPY_BASELINE")
        if audit_stage_c.audit(working)["status"]!="PASS":
            raise RuntimeError("PREIMPORT_COPY_STAGE_C_FAILED")
        sync_result,used=run_incremental_on_copy(
            working,source,rows,inventory_qa,fresh_bodies,
        )
        updated=load(working/"indexes/integrated/meetings.json")
        updated_by_id={str(r["source_id"]):r for r in updated}
        if len(updated)!=2341 or len(updated_by_id)!=2341:
            raise RuntimeError("NEW_COUNT_OR_DUPLICATE_AFTER_IMPORT")
        old_unchanged=verify_original_bytes(working,source)
        new_checks=[]
        for sid in EXPECTED:
            new=updated_by_id[sid]
            if (new["term"]!=4 or new["publication_status"]!="provisional"
                or new["inventory_sources"]!=["term","year"]
                or new["content_sha256"]!=NEW_BODY_SHA[sid]
                or digest(working/new["path"])!=new["sha256"]):
                raise RuntimeError("NEW_OFFICIAL_ORIGINAL_NOT_COHERENT: "+sid)
            new_checks.append({
                "source_id":sid,
                "canonical_path":new["path"],
                "raw_markdown_sha256":new["sha256"],
                "normalized_official_body_sha256":new["content_sha256"],
                "body_match":True,
            })
        qa=audit_stage_c.audit(working)
        if qa["status"]!="PASS" or qa["source_rows"]!=2341:
            raise RuntimeError("STAGE_C_2341_FULL_COPY_FAILED: "+repr(qa["errors"][:12]))
        manifest=load(working/"exports/analyzer/manifest.json")
        meeting_export=manifest["datasets"]["meetings"]
        if meeting_export["rows"]!=2341 or qa["export_rows_checked"]!=2341:
            raise RuntimeError("ANALYZER_MEETING_EXPORT_NOT_2341")
        if qa["published"]!=2333 or qa["provisional"]!=8:
            raise RuntimeError("POST_IMPORT_PUBLICATION_COUNTS_UNEXPECTED")
        if qa["by_term"] != {"1":663,"2":771,"3":855,"4":52}:
            raise RuntimeError("POST_IMPORT_TERM_COUNTS_UNEXPECTED")
        if len(used)!=8 or sorted(used,key=int)!=["4017","4018","4019","4020","4021","4022","4024","4025"]:
            raise RuntimeError("NON_BOUNDED_INCREMENTAL_BODY_REPLAY")
        crash=sigkill_and_recover(copied_before_crash,working,source)

        result.update({
            "status":"PASS",
            "read_only_official_gets":2,
            "source_added_into_disposable_copy":new_checks,
            "copy_new_source_ids":[sid for sid in EXPECTED],
            "copy_existing_sources_byte_identical":old_unchanged,
            "copy_source_count":qa["source_rows"],
            "copy_published":qa["published"],
            "copy_provisional":qa["provisional"],
            "copy_by_term":qa["by_term"],
            "copy_sha256_files_verified":qa["sha256_file_verified"],
            "copy_sha256_bodies_verified":qa["sha256_content_verified"],
            "copy_analyzer_meeting_rows":meeting_export["rows"],
            "copy_export_manifest_sha_verified":qa["export_files_hash_verified"],
            "copy_stage_c_result":qa["status"],
            "copy_stage_c_warning_count":qa["warning_count"],
            "copy_stage_c_errors":qa["errors"][:10],
            "six_unchanged_provisional_bodies_replayed_from_saved_source":True,
            "eight_mocked_fetch_url_lookups_to_saved_or_live_verified_body_map":used,
            "canonical_sync_report_new_ids":sync_result["new"],
            "canonical_sync_report_bodies_checked":sync_result["bodies_checked"],
            "crash_recovery":crash,
            "temp_copies_removed_after_run":True,
        })
    # Repository source originals and derivations cannot have changed.
    if (digest(INDEX)!=original_index_hash
        or digest(ROOT/"exports/analyzer/meetings.jsonl")!=original_export_hash
        or digest(ROOT/"exports/analyzer/manifest.json")!=original_manifest_hash):
        raise RuntimeError("PRODUCTION_REPO_INDEX_OR_EXPORT_MODIFIED")
    if audit_stage_c.audit(ROOT)["status"]!="PASS":
        raise RuntimeError("PRODUCTION_REPO_SOURCE_QA_FAILED_POST_REHEARSAL")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


if __name__ == "__main__":
    run()
