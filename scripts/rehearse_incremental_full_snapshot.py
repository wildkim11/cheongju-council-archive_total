"""Offline rehearsal of an incremental update over a COPY of all 2,339 stored meetings.

Never contacts the official website and never writes to the checked-out source
archive. Uses a disposable root, mocked source inventory and six original
provisional meeting bodies restored exactly from their archived Markdown.
The 2,340th record is SYNTHETIC and never becomes an official source record.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import collect_integrated_minutes as c
import audit_stage_c

ROOT=Path(__file__).resolve().parents[1]
TEST_ID="98765432"
TEST_MID=f"cheongju_integrated:minutes-{TEST_ID}"

def sha(path:Path)->str:
    d=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            d.update(block)
    return d.hexdigest()

def read(path:Path):
    return json.loads(path.read_text(encoding="utf-8"))

def run():
    base=read(ROOT/"indexes/integrated/meetings.json")
    if len(base)!=2339 or any(str(row.get("source_id"))==TEST_ID for row in base):
        raise RuntimeError("Refusing full rehearsal: original 2339 snapshot precondition not met")
    source_hashes={str(row["source_id"]):row["sha256"] for row in base}
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="cheongju-sync-full-copy-") as folder:
        fixture=Path(folder)/"isolated-root"
        fixture.mkdir()
        for folder_name in ("archive","indexes","reports","exports"):
            original=ROOT/folder_name
            if original.is_dir():
                shutil.copytree(original,fixture/folder_name)
        before=read(fixture/"indexes/integrated/meetings.json")
        if before!=base:
            raise RuntimeError("Synthetic test fixture not an exact canonical index copy")
        current_qa=audit_stage_c.audit(fixture)
        if current_qa["status"]!="PASS":
            raise RuntimeError("Baseline copied 2339 snapshot did not pass integrity QA: "
                               + ";".join(current_qa["errors"][:5]))

        synthetic={
            "meeting_id":TEST_MID,
            "legacy_minutes_id":f"minutes-{TEST_ID}",
            "council_scope":"cheongju_integrated",
            "term":4,
            "title":"제4대 의회 시험 회의록(2026.11.02 월요일) 본회의 제1차(2026.11.02 월요일)",
            "date":"2026-11-02",
            "year":2026,
            "committee_code":"A010",
            "meeting_type":"plenary",
            "publication_status":"published",
            "official_url":c.BASE+"/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn="+TEST_ID,
            "source_id":TEST_ID,
            "inventory_sources":["term","year"],
        }
        body_by_id={
            TEST_ID:"○위원장 시험\n"+"완전히 가상인 테스트 기록이며 실제 공식 회의록에 포함하지 않습니다. "*30
        }
        for row in base:
            if row["publication_status"]!="provisional":
                continue
            md=(fixture/row["path"]).read_text(encoding="utf-8")
            _title,_metadata,original_body=audit_stage_c.markdown_parts(md)
            body_by_id[str(row["source_id"])]=original_body
        if len(body_by_id)!=7:
            raise RuntimeError("Expected one synthetic plus six saved provisional bodies")
        live=sorted([{k:v for k,v in row.items() if k not in (
            "path","content_sha256","sha256","bytes","first_seen_at",
            "last_checked_at","supersedes","superseded_by")}
                     for row in base]+[synthetic],
                    key=lambda row:(row["date"],row["meeting_id"]))
        except_ids=read(ROOT/"reports/integrated-sync.json")["inventory_qa"]["only_term"]
        qa={
            "term_inventory_count":2340,
            "year_inventory_count":2340-len(except_ids),
            "shared_count":2340-len(except_ids),
            "only_term":except_ids,
            "only_year":[],
        }
        requests=[]
        def fetch_stub(url):
            sid=url.rsplit("schSn=",1)[-1]
            if sid not in body_by_id:
                raise AssertionError("Unmocked source read: "+str(sid))
            requests.append(sid)
            return sid
        def parse_stub(sid):
            return body_by_id[sid]
        with patch.object(c,"read_official_inventory",return_value=(live,qa)), \
             patch.object(c,"fetch",side_effect=fetch_stub), \
             patch.object(c,"extract_minutes_body",side_effect=parse_stub):
            report=c.run_sync("incremental",fixture)
        index=read(fixture/"indexes/integrated/meetings.json")
        by_id={str(row["source_id"]):row for row in index}
        originals_equal=all(
            by_id[sid]["sha256"]==hashv
            and sha(fixture/by_id[sid]["path"])==hashv
            for sid,hashv in source_hashes.items()
        )
        final_qa=audit_stage_c.audit(fixture)
        updated_manifest=read(fixture/"exports/analyzer/manifest.json")
        synth_count=sum(str(row["source_id"])==TEST_ID for row in index)
        data={
            "generated_at_utc":now,
            "status":"PASS" if (
                len(index)==2340 and synth_count==1 and originals_equal
                and final_qa["status"]=="PASS"
                and updated_manifest["datasets"]["meetings"]["rows"]==2340
                and read(fixture/"indexes/integrated/meeting_revisions.json")==[]
                and report["new"]==[TEST_MID]
                and len(requests)==7
            ) else "FAIL",
            "mode":"offline disposable COPY of original archive; official HTTP fully mocked",
            "original_source_meetings":2339,
            "synthetic_added_meetings":synth_count,
            "fixture_post_sync_count":len(index),
            "old_source_bytes_hash_preserved":originals_equal,
            "original_source_unchanged_count":sum(
                by_id[sid]["sha256"]==hashv for sid,hashv in source_hashes.items()),
            "original_provisional_refetched_from_local_markdown":len(requests)-1,
            "synthetic_data_only":True,
            "official_site_requests":0,
            "fixture_stage_c_qa_status":final_qa["status"],
            "fixture_stage_c_qa_errors":final_qa["errors"][:15],
            "fixture_stage_c_verified_source_files":final_qa["source_files_checked"],
            "derived_meetings_export_rows":updated_manifest["datasets"]["meetings"]["rows"],
            "original_check_out_archives_modified":False,
            "production_sync_interlock_still_active":True,
            "original_snapshot_url":"development-branch saved 2339 meeting archive",
        }
        if data["status"]!="PASS":
            raise AssertionError(json.dumps(data,ensure_ascii=False,indent=2))
    path=ROOT/"reports/incremental-full-snapshot-rehearsal.json"
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(data,ensure_ascii=False,indent=2))
    return data

if __name__=="__main__":
    run()
