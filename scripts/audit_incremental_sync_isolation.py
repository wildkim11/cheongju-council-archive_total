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
            for p in root.rglob("*") if p.is_file()}

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
        derived_untouched=hashlib.sha256((root/"exports/analyzer/meetings.jsonl").read_bytes()).hexdigest()==manifest_hash
        shard_count=len(read_json(root/"indexes/integrated/initial_term_4.json"))
        return {
            "added_new_source":new["meeting_id"] in ids,
            "original_markdown_unchanged":copied,
            "derived_meetings_export_stale":derived_untouched,
            "term_shard_stale":shard_count!=len(ids),
            "reported_new":report["new"],
        }

def scenario_same_id_status_transition():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        old=row(903,publication_status="provisional")
        fixture(root,[old])
        live=row(903,publication_status="published")
        sync(root,[live])
        idx=read_json(root/"indexes/integrated/meetings.json")[0]
        source=(root/idx["path"]).read_text(encoding="utf-8")
        return {
            "indexed_publication_status":idx["publication_status"],
            "markdown_publication_status":(
                "published" if "- publication_status: published" in source else
                "provisional" if "- publication_status: provisional" in source else "missing"
            ),
            "index_markdown_status_mismatch":idx["publication_status"]=="published" and "- publication_status: provisional" in source,
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
        history=read_json(root/"indexes/integrated/meeting_history.json")
        return {
            "same_path_overwritten":before["path"]==after["path"] and raw_before!=raw_after,
            "old_bytes_not_preserved_in_history":len(history)==0,
            "changed_ids":report["changed"],
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
        copy_source=c.shutil.copyfile
        error=None
        def fail_on_index(src,dst,*args,**kwargs):
            if Path(dst).is_relative_to(root) and Path(dst).as_posix().endswith("indexes/integrated/meetings.json"):
                raise OSError("simulated disk/publish failure")
            return copy_source(src,dst,*args,**kwargs)
        try:
            sync(root,[old,row(908,date="2026-10-02")],copy_impl=fail_on_index)
        except OSError as exc:
            error=type(exc).__name__
        after=snapshot(root)
        return {
            "error_propagated":error=="OSError",
            "partial_publication_mutated_destination":after!=before,
            "new_markdown_exists":(root/"archive/meetings/cheongju_integrated/term-4/2026/minutes-908.md").exists(),
            "canonical_index_unchanged":read_json(root/"indexes/integrated/meetings.json")[0]["source_id"]=="907"
                and len(read_json(root/"indexes/integrated/meetings.json"))==1,
        }

def scenario_colliding_replacements():
    old=[row(909,publication_status="provisional"),row(910,publication_status="provisional")]
    new=row(911,publication_status="published",date="2026-10-02")
    result=c.detect_replacements(old,[new])
    return {
        "distinct_missing_provisionals":len(old),
        "same_successor_assigned_more_than_once":len(result)>len(set(result.values())),
        "mapping":result,
    }

def diagnose():
    results={
        "new_and_derived":scenario_add_and_derived(),
        "same_id_status":scenario_same_id_status_transition(),
        "same_id_body":scenario_same_id_body_revision(),
        "remote_failure":scenario_fetch_failure(),
        "publish_failure":scenario_publish_copy_failure(),
        "colliding_replacements":scenario_colliding_replacements(),
    }
    blocks={
        "derived_exports_and_shards_not_updated":results["new_and_derived"]["derived_meetings_export_stale"] and results["new_and_derived"]["term_shard_stale"],
        "same_id_publication_status_header_inconsistent":results["same_id_status"]["index_markdown_status_mismatch"],
        "original_bytes_overwritten_on_same_id_revisions":results["same_id_body"]["same_path_overwritten"] and results["same_id_body"]["old_bytes_not_preserved_in_history"],
        "publish_failure_leaves_partial_target":results["publish_failure"]["partial_publication_mutated_destination"] and results["publish_failure"]["canonical_index_unchanged"],
        "many_to_one_provisional_replacements_allowed":results["colliding_replacements"]["same_successor_assigned_more_than_once"]
    }
    return {
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode":"isolated temporary fixture, network fully mocked",
        "scenarios":results,
        "successes":{
            "new_markdown_appended_without_editing_old_source":results["new_and_derived"]["added_new_source"] and results["new_and_derived"]["original_markdown_unchanged"],
            "remote_fetch_failure_aborts_without_writes":results["remote_failure"]["error_propagated"] and results["remote_failure"]["fixture_unchanged"],
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
