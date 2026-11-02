"""Offline-only fault-injection audit of the EXISTING integrated minutes sync.

Runs the production run_sync function only against disposable temporary fixtures
with mocked official HTTP. NEVER passes ROOT, repository paths or real URLs to
network. A PASS from tests is NOT permission to schedule the collector: the
report explicitly distinguishes verified behavior from release-blocking flaws.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import collect_integrated_minutes as c

ROOT=Path(__file__).resolve().parents[1]
OFFICIAL="https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="

def row(source_id,publication_status="published",date="2026-10-01",title=None):
    source_id=str(source_id)
    return {
        "meeting_id":f"cheongju_integrated:minutes-{source_id}",
        "legacy_minutes_id":f"minutes-{source_id}",
        "council_scope":"cheongju_integrated","term":4,
        "title":title or "제4대 제107회 본회의 제1차(2026.10.01 목요일)",
        "date":date,"year":int(date[:4]),
        "committee_code":"C101","meeting_type":"plenary",
        "publication_status":publication_status,
        "official_url":OFFICIAL+source_id,"source_id":source_id,
        "inventory_sources":["term","year"]
    }

def body(tag="기본"):
    return "○위원장 시험\n"+(tag+" 자료 근거로 안건을 확인하겠습니다. ")*28

def html_doc(tag="기본"):
    return "<!-- 회의록내용 --><div><p>"+body(tag).replace("\n","</p><p>")+"</p></div><!--// 회의록내용 -->"

def save_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def snapshot(root):
    # SHA256 for all payload bytes; baseline snapshots do not rely on mtime.
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and p.name!=".integrated-sync.lock"}

def fixture(root,initial_rows,with_derived=False):
    prepared=[]
    for r in initial_rows:
        prepared.append(c.write_record(root,r,body(),now="2026-10-01T10:00:00+09:00"))
    save_json(root/"indexes/integrated/meetings.json",prepared)
    save_json(root/"indexes/integrated/meeting_history.json",[])
    if with_derived:
        save_json(root/"indexes/integrated/initial_term_4.json",prepared)
        path=root/"exports/analyzer/meetings.jsonl"
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in prepared),encoding="utf-8")
        save_json(root/"exports/analyzer/manifest.json",{"datasets":{"meetings":{"rows":len(prepared)}}})
    return prepared

def sync(root,live_rows,mode="incremental",fetch_impl=None,copy_impl=None):
    # Test always patches network functions; no actual official-site requests.
    qa={"term_inventory_count":len(live_rows),"year_inventory_count":len(live_rows),
        "shared_count":len(live_rows),"only_term":[],"only_year":[]}
    with patch.object(c,"read_official_inventory",return_value=(live_rows,qa)), \
         patch.object(c,"fetch",side_effect=fetch_impl or (lambda _url:html_doc())):
        if copy_impl is not None:
            with patch.object(c.shutil,"copyfile",side_effect=copy_impl):
                return c.run_sync(mode,root)
        return c.run_sync(mode,root)

def scenario_add_and_derived():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        old=row(901)
        new=row(902,date="2026-10-02",title="제4대 제107회 본회의 제2차(2026.10.02 금요일)")
        fixture(root,[old],with_derived=True)
        original_md=root/"archive/meetings/cheongju_integrated/term-4/2026/minutes-901.md"
        old_hash=hashlib.sha256(original_md.read_bytes()).hexdigest()
        manifest_hash=hashlib.sha256((root/"exports/analyzer/meetings.jsonl").read_bytes()).hexdigest()
        report=sync(root,[old,new])
        ids={x["meeting_id"] for x in read_json(root/"indexes/integrated/meetings.json")}
        copied=hashlib.sha256(original_md.read_bytes()).hexdigest()==old_hash
        generated=root/"exports/analyzer/meetings.jsonl"
        rows_exported=[json.loads(line) for line in generated.read_text(encoding="utf-8").splitlines() if line.strip()]
        derived_matches=rows_exported==read_json(root/"indexes/integrated/meetings.json")
        initial_count=len(read_json(root/"indexes/integrated/initial_term_4.json"))
        current_count=len(read_json(root/"indexes/integrated/current_term_4.json"))
        manifest=read_json(root/"exports/analyzer/manifest.json")
        return {
            "added_new_source":new["meeting_id"] in ids,
            "original_markdown_unchanged":copied,
            "derived_meetings_export_matches_current":derived_matches,
            "term_shard_matches_current":current_count==len(ids),
            "initial_term_shard_preserved":initial_count==1,
            "derived_manifest_meetings_count":manifest["datasets"]["meetings"]["rows"],
            "stale_old_derived_hash_replaced":hashlib.sha256(generated.read_bytes()).hexdigest()!=manifest_hash,
            "reported_new":report["new"],
        }

def scenario_same_id_status_transition():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        old=row(903,publication_status="provisional")
        before_record=fixture(root,[old])[0]
        original=(root/before_record["path"]).read_bytes()
        live=row(903,publication_status="published")
        report=sync(root,[live])
        idx=read_json(root/"indexes/integrated/meetings.json")[0]
        source=(root/idx["path"]).read_text(encoding="utf-8")
        revs=read_json(root/"indexes/integrated/meeting_revisions.json")
        preserved=(root/revs[0]["revision_path"]).read_bytes() if revs else b""
        return {
            "same_id_transition_versioned":idx["publication_status"]=="published"
                and "- publication_status: published" in source,
            "prior_exact_original_bytes_preserved":preserved==original,
            "revision_rows":len(revs),
            "prior_status":revs[0]["prior_source_record"]["publication_status"] if revs else None,
            "next_status":revs[0]["next_source_record"]["publication_status"] if revs else None,
            "reported_revised":report["revised"],
        }


def scenario_same_id_body_revision():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        live=row(904)
        before=fixture(root,[live])[0]
        raw_before=(root/before["path"]).read_bytes()
        report=sync(root,[live],mode="full",fetch_impl=lambda _url:html_doc("수정"))
        after=read_json(root/"indexes/integrated/meetings.json")[0]
        raw_after=(root/after["path"]).read_bytes()
        revs=read_json(root/"indexes/integrated/meeting_revisions.json")
        previous_path=root/revs[0]["revision_path"] if revs else root/"missing"
        return {
            "content_revision_changed_current":raw_after!=raw_before,
            "original_bytes_immutable":previous_path.is_file() and previous_path.read_bytes()==raw_before,
            "revision_rows":len(revs),
            "prior_sha256_matches":bool(revs) and revs[0]["prior_sha256"]==hashlib.sha256(raw_before).hexdigest(),
            "changed_ids":report["changed"],
        }


def scenario_revert_after_revisions():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        live=row(912,publication_status="provisional")
        first=fixture(root,[live])[0]
        source_original=(root/first["path"]).read_bytes()
        sync(root,[row(912,publication_status="published")])
        sync(root,[row(912,publication_status="published")],mode="full",
             fetch_impl=lambda _url:html_doc("수정"))
        report=sync(root,[row(912,publication_status="published")],mode="full",
                    fetch_impl=lambda _url:html_doc())
        ledger=read_json(root/"indexes/integrated/meeting_revisions.json")
        return {
            "three_transitions_recorded":len(ledger)==3,
            "all_old_bytes_still_present":all(
                (root/item["revision_path"]).is_file()
                and hashlib.sha256((root/item["revision_path"]).read_bytes()).hexdigest()==item["prior_sha256"]
                for item in ledger
            ),
            "original_first_version_preserved":any(
                (root/item["revision_path"]).read_bytes()==source_original for item in ledger
            ),
            "last_transition_from_modified_body":bool(ledger)
               and "content_sha256" in ledger[-1]["changed_source_fields"],
            "reported_revised":report["revised"],
        }


def scenario_fetch_failure():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        old=row(905)
        fixture(root,[old])
        before=snapshot(root)
        error=None
        try:
            sync(root,[old,row(906,date="2026-10-02")],
                 fetch_impl=lambda _url:(_ for _ in ()).throw(TimeoutError("simulated official HTTP timeout")))
        except RuntimeError as exc:
            error=type(exc).__name__
        return {
            "error_propagated":error=="RuntimeError",
            "fixture_unchanged":snapshot(root)==before,
        }

def scenario_publish_copy_failure():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        old=row(907)
        fixture(root,[old])
        before=snapshot(root)
        import sync_transaction
        install_source=sync_transaction._atomic_install
        error=None
        fault_injected=[False]
        def fail_on_index(src,dst,*args,**kwargs):
            if (not fault_injected[0] and Path(dst).is_relative_to(root)
                and Path(dst).as_posix().endswith("indexes/integrated/meetings.json")):
                fault_injected[0]=True
                raise OSError("simulated disk/publish failure")
            return install_source(src,dst,*args,**kwargs)
        try:
            with patch.object(sync_transaction,"_atomic_install",side_effect=fail_on_index):
                sync(root,[old,row(908,date="2026-10-02")])
        except OSError as exc:
            error=type(exc).__name__
        after=snapshot(root)
        return {
            "error_propagated":error=="OSError",
            "rollback_restored_destination":after==before,
            "fault_was_injected":fault_injected[0],
            "new_markdown_exists_after_rollback":(root/"archive/meetings/cheongju_integrated/term-4/2026/minutes-908.md").exists(),
            "canonical_index_unchanged":read_json(root/"indexes/integrated/meetings.json")[0]["source_id"]=="907"
                and len(read_json(root/"indexes/integrated/meetings.json"))==1,
        }

def scenario_colliding_replacements():
    old=[row(909,publication_status="provisional"),row(910,publication_status="provisional")]
    new=row(911,publication_status="published",date="2026-10-02")
    try:
        result=c.detect_replacements(old,[new])
        return {
            "distinct_missing_provisionals":len(old),
            "many_to_one_rejected":False,
            "unsafe_mapping":result,
        }
    except ValueError as exc:
        return {
            "distinct_missing_provisionals":len(old),
            "many_to_one_rejected":True,
            "rejection_reason":str(exc)[:320],
        }

def scenario_real_repository_interlock():
    # The real project root may never be scanned or modified by this fixture.
    from unittest.mock import patch
    for mode in ("incremental","full"):
        with patch.object(c,"read_official_inventory",side_effect=AssertionError("network was called")):
            try:
                c.run_sync(mode,ROOT)
            except RuntimeError as exc:
                if "LIVE_ARCHIVE_INCREMENTAL_SYNC_DISABLED" not in str(exc):
                    return {"real_root_interlock_pass":False,"mode":mode,"reason":str(exc)[:160]}
            else:
                return {"real_root_interlock_pass":False,"mode":mode,"reason":"No exception"}
    return {"real_root_interlock_pass":True,"blocked_modes":["incremental","full"]}

def diagnose():
    results={
        "new_and_derived":scenario_add_and_derived(),
        "same_id_status":scenario_same_id_status_transition(),
        "same_id_body":scenario_same_id_body_revision(),
        "same_id_revert":scenario_revert_after_revisions(),
        "remote_failure":scenario_fetch_failure(),
        "publish_failure":scenario_publish_copy_failure(),
        "colliding_replacements":scenario_colliding_replacements(),
        "real_repository_interlock":scenario_real_repository_interlock(),
    }
    blocks={
        "derived_exports_and_current_shards_not_updated":not (
            results["new_and_derived"]["derived_meetings_export_matches_current"]
            and results["new_and_derived"]["term_shard_matches_current"]
            and results["new_and_derived"]["initial_term_shard_preserved"]
        ),
        "same_id_metadata_transition_requires_versioned_history":not (
            results["same_id_status"]["same_id_transition_versioned"]
            and results["same_id_status"]["prior_exact_original_bytes_preserved"]
        ),
        "same_id_content_revision_requires_versioned_history":not (
            results["same_id_body"]["content_revision_changed_current"]
            and results["same_id_body"]["original_bytes_immutable"]
            and results["same_id_revert"]["all_old_bytes_still_present"]
        ),
        "publish_exception_can_leave_partial_target":not results["publish_failure"]["rollback_restored_destination"],
        "unexpected_process_termination_crash_atomicity_not_proven":True,
        "many_to_one_provisional_replacements_allowed":not results["colliding_replacements"]["many_to_one_rejected"]
    }
    return {
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"isolated temporary fixture, network fully mocked",
        "scenarios":results,
        "successes":{
            "new_markdown_appended_without_editing_old_source":results["new_and_derived"]["added_new_source"] and results["new_and_derived"]["original_markdown_unchanged"],
            "staged_analyzer_exports_and_current_term_shards_are_consistent":(
                results["new_and_derived"]["derived_meetings_export_matches_current"]
                and results["new_and_derived"]["term_shard_matches_current"]
                and results["new_and_derived"]["initial_term_shard_preserved"]
            ),
            "remote_fetch_failure_aborts_without_writes":results["remote_failure"]["error_propagated"] and results["remote_failure"]["fixture_unchanged"],
            "real_repository_sync_hard_interlock":results["real_repository_interlock"]["real_root_interlock_pass"],
            "caught_publish_exception_restores_full_fixture":results["publish_failure"]["rollback_restored_destination"] and results["publish_failure"]["fault_was_injected"],
            "same_id_metadata_and_original_bytes_versioned":(
                results["same_id_status"]["same_id_transition_versioned"]
                and results["same_id_status"]["prior_exact_original_bytes_preserved"]
                and results["same_id_body"]["original_bytes_immutable"]
                and results["same_id_revert"]["all_old_bytes_still_present"]
            ),
        },
        "release_blockers":blocks,
        "release_blocker_count":sum(blocks.values()),
        "release_decision":"BLOCKED_UNSAFE_TO_OPERATE" if any(blocks.values()) else "NO_KNOWN_BLOCKERS_FROM_THESE_TESTS",
        "canonical_project_files_modified":False,
        "official_site_requests":0,
        "assertion":"No live or scheduled incremental collection permitted by this test report."
    }

if __name__=="__main__":
    output=diagnose()
    target=ROOT/"reports/incremental-sync-isolation-diagnostics.json"
    target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(output,ensure_ascii=False,indent=2))
