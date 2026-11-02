"""Compose verified offline version/crash/full-copy source-only release gate.

Called only after CI ran full all-tests, source archive audit, synthetic
full-archive rehearsal. Independently re-runs actual SIGKILL subprocess tests
before claiming that recovery case was exercised on this same runner.
"""
from __future__ import annotations
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(relative):
    return json.loads((ROOT/relative).read_text(encoding="utf-8"))

def build():
    isolation=load("reports/incremental-sync-isolation-diagnostics.json")
    full=load("reports/incremental-full-snapshot-rehearsal.json")
    process=subprocess.run(
        [sys.executable,"-m","unittest","discover","-s","tests",
         "-p","test_sync_transaction_crash.py","-v"],
        cwd=ROOT,capture_output=True,text=True,timeout=120,
    )
    details=process.stdout+"\n"+process.stderr
    match=re.search(r"Ran (\d+) tests",details)
    case_count=int(match[1]) if match else 0
    if process.returncode!=0 or case_count<6 or "OK" not in details:
        raise RuntimeError("SIGKILL crash-restart recovery test suite did not pass: "+details[-2000:])
    if not all(isolation["successes"].values()):
        raise RuntimeError("Not all offline source preservation checks passed")
    if isolation["release_blockers"].get("hardware_power_loss_atomicity_not_certified") is not True:
        raise RuntimeError("Must not claim actual electrical power-loss hardware certification")
    for key in ("same_id_metadata_transition_requires_versioned_history",
                "same_id_content_revision_requires_versioned_history",
                "publish_exception_can_leave_partial_target",
                "many_to_one_provisional_replacements_allowed",
                "derived_exports_and_current_shards_not_updated"):
        if isolation["release_blockers"].get(key) is not False:
            raise RuntimeError("Corrected source preservation condition regressed: "+key)
    if (full["status"]!="PASS" or full["original_source_meetings"]!=2339
        or full["fixture_post_sync_count"]!=2340 or not full["old_source_bytes_hash_preserved"]
        or full["fixture_stage_c_qa_status"]!="PASS"
        or full["fixture_stage_c_verified_source_files"]!=2340
        or full["derived_meetings_export_rows"]!=2340
        or full["official_site_requests"]!=0
        or not isolation["successes"]["real_repository_sync_hard_interlock"]):
        raise RuntimeError("Full snapshot rehearsal or live-root interlock failed")
    if isolation["official_site_requests"]!=0 or isolation["canonical_project_files_modified"]:
        raise RuntimeError("Unexpected live data access or source modification")
    output={
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "status":"OFFLINE_SAFETY_TESTS_PASS_PRODUCTION_LOCKED",
        "production_collection_enabled":False,
        "canonical_archive_modified":False,
        "official_http_requests":0,
        "same_id_metadata_revision_immutable_originals_verified":True,
        "same_id_body_revision_and_revert_immutable_originals_verified":True,
        "crash_restart_recovery":{
            "mechanism":"real SIGKILL child processes followed by fresh-process recovery",
            "test_count":case_count,
            "pass":True,
            "uncommitted_journal_restored_old_bytes":True,
            "committed_journal_retained_new_bytes":True,
            "corrupted_preimage_detection_refuses_unsafe_recovery":True,
            "concurrent_writer_local_posix_lock_tested":True,
            "hardware_power_loss_tested":False,
        },
        "saved_full_snapshot_rehearsal":{
            "official_saved_originals":2339,
            "original_file_hashes_unchanged":True,
            "synthetic_added":1,
            "temporary_snapshot_count":2340,
            "stage_c_qa_verified_source_files":2340,
            "source_canonical_files_modified":False,
        },
        "release_gates_remaining":[
            "Live official site inventory and incremental retry/load must undergo a separate controlled, read-only pilot",
            "Same-ID date/term edits that change canonical original path are fail-closed pending versioned migration",
            "Physical power-loss, unsupported/network filesystems and non-cooperating writers not certified",
            "Explicit approval to unlock production ROOT or schedule automatic updates not given"
        ],
        "source_test_files":[
            "tests/test_sync_transaction_crash.py",
            "tests/test_incremental_sync_isolation.py",
            "scripts/audit_incremental_sync_isolation.py",
            "scripts/rehearse_incremental_full_snapshot.py",
        ],
        "assertion":"An offline PASS does not authorize actual Cheongju City Council incremental harvesting.",
    }
    path=ROOT/"reports/incremental-revision-crash-release-gate.json"
    path.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return output

if __name__=="__main__":
    build()
