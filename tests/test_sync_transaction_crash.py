"""Real OS SIGKILL process termination and restart tests (isolated temp roots).

The child process sends itself SIGKILL, skipping cleanup/finally and leaving a real
write-ahead journal on disk. A separate parent invocation restores/finalizes.
No official website and NO canonical GitHub archive source is ever modified.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS=Path(__file__).resolve().parents[1]/"scripts"
sys.path.insert(0,str(SCRIPTS))
import sync_transaction as tx


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fixture(root,stage):
    old={"indexes/integrated/meetings.json":b'{"old":true}\n',
         "archive/meetings/cheongju_integrated/term-4/2026/minutes-1.md":b"# retained old official minutes\n"}
    new={"indexes/integrated/meetings.json":b'{"new":true}\n',
         "archive/meetings/cheongju_integrated/term-4/2026/minutes-1.md":b"# changed current official minutes\n",
         "exports/analyzer/meetings.jsonl":b'{"new":true}\n'}
    for rel,content in old.items():
        file=root/rel
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_bytes(content)
    for rel,content in new.items():
        file=stage/rel
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_bytes(content)
    return old,new


def children_snapshot(root):
    return {p.relative_to(root).as_posix():digest(p) for p in root.rglob("*")
            if p.is_file() and p.name!=tx.LOCK and not tx.JOURNAL in p.parts}


def abrupt_exit(root,stage,point):
    script=r'''
import os,sys,signal
from pathlib import Path
import sync_transaction as tx
root,stage=Path(sys.argv[1]),Path(sys.argv[2])
phase_to_kill=sys.argv[3]
def trigger(phase,count):
    if phase==phase_to_kill and (phase!="installed" or count==1):
        os.kill(os.getpid(),signal.SIGKILL)
with tx.exclusive_lock(root):
    tx.publish_staged_snapshot(stage,root,on_phase=trigger)
raise RuntimeError("Phase was not hit; expected process exit")
'''
    env={**os.environ,"PYTHONPATH":str(SCRIPTS)}
    return subprocess.run([sys.executable,"-c",script,str(root),str(stage),point],
                          capture_output=True,text=True,env=env,timeout=20)


class CrashRecoveryTests(unittest.TestCase):
    def _case(self,point,expected_status,expected_after):
        with tempfile.TemporaryDirectory() as folder:
            temp=Path(folder)
            root=temp/"working"
            stage=temp/"fully-validated-stage"
            root.mkdir()
            stage.mkdir()
            old,new=source_fixture(root,stage)
            baseline=children_snapshot(root)
            p=abrupt_exit(root,stage,point)
            self.assertEqual(p.returncode,-signal.SIGKILL,p.stderr)
            self.assertTrue((root/tx.JOURNAL/"manifest.json").is_file())
            with tx.exclusive_lock(root):
                out=tx.recover_pending(root)
            self.assertEqual(out["status"],expected_status)
            self.assertEqual(out["files"],3)
            self.assertFalse((root/tx.JOURNAL).exists())
            self.assertEqual(tx.recover_pending(root)["status"],"clean")
            if expected_after=="old":
                self.assertEqual(children_snapshot(root),baseline)
                for rel,raw in old.items():
                    self.assertEqual((root/rel).read_bytes(),raw)
                self.assertFalse((root/"exports/analyzer/meetings.jsonl").exists())
            else:
                for rel,raw in new.items():
                    self.assertEqual((root/rel).read_bytes(),raw)
                self.assertEqual(len(children_snapshot(root)),len(new))

    def test_exit_after_durable_journal_before_first_write(self):
        self._case("prepared","rolled_back_uncommitted","old")

    def test_abrupt_exit_after_one_file_updated_restores_every_old_byte(self):
        self._case("installed","rolled_back_uncommitted","old")

    def test_abrupt_exit_after_commit_marker_finalizes_without_rollback(self):
        self._case("committed","finished_committed","new")

    def test_corrupted_backup_does_not_silently_erase_originals(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"working"
            stage=Path(folder)/"stage"
            root.mkdir()
            stage.mkdir()
            source_fixture(root,stage)
            p=abrupt_exit(root,stage,"installed")
            self.assertEqual(p.returncode,77,p.stderr)
            backup=root/tx.JOURNAL/"old/indexes/integrated/meetings.json"
            backup.write_bytes(b"tampered")
            before=children_snapshot(root)
            with tx.exclusive_lock(root):
                with self.assertRaisesRegex(RuntimeError,"BACKUP_MISSING_OR_CORRUPT"):
                    tx.recover_pending(root)
            self.assertEqual(children_snapshot(root),before)
            self.assertTrue((root/tx.JOURNAL).exists())

    def test_lock_rejects_competing_writer(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with tx.exclusive_lock(root):
                with self.assertRaisesRegex(RuntimeError,"CONCURRENT_WRITER_BLOCKED"):
                    with tx.exclusive_lock(root):
                        pass

    def test_journal_recovery_path_validation_rejects_traversal(self):
        for path in ("/tmp/evil","../escape.md","archive/../../foo","other/../archive/a"):
            with self.assertRaises(ValueError,msg=path):
                tx._safe_relative(path)

if __name__=="__main__":
    unittest.main()
