"""Crash-recoverable journal for an isolated, staged archive snapshot publisher.

All writes happen to a transaction journal before touching target files.
A manifest seals complete pre-images and post-images, then publishing uses an
atomic per-file rename. Recovery replays an uncommitted journal BACK to the
old snapshot, or retains a committed journal after verifying new hashes.

POSIX filesystem semantics are required (fsync, os.replace, fcntl flock).
Crash tests run in disposable roots. The real archive remains hard blocked
at collect_integrated_minutes.run_sync until separate approval.

A lock serializes publisher/recovery in a single local filesystem. Shared
network filesystem durability, hardware failure, and concurrent non-cooperating
writers are NOT certified by these tests.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Callable

JOURNAL=".integrated-sync-journal"
LOCK=".integrated-sync.lock"
DRAFT_PREFIX=".integrated-sync-draft-"
ALLOW_ROOT={"archive","indexes","reports","exports"}
MANIFEST="manifest.json"
COMMITTED="committed.json"


def sha(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(1024*1024),b""):
            digest.update(part)
    return digest.hexdigest()


def fsync_dir(path:Path)->None:
    fd=os.open(path,os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_json_atomic(dest:Path, value:dict)->None:
    dest.parent.mkdir(parents=True,exist_ok=True)
    body=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    fd,name=tempfile.mkstemp(prefix=".sync-tmp-",dir=dest.parent)
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name,dest)
        fsync_dir(dest.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _atomic_install(source:Path,dest:Path)->None:
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=".sync-tmp-",dir=dest.parent)
    try:
        with source.open("rb") as inp, os.fdopen(fd,"wb") as out:
            shutil.copyfileobj(inp,out,length=1024*1024)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name,dest)
        fsync_dir(dest.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _safe_relative(relative:str)->Path:
    if not isinstance(relative,str) or not relative:
        raise ValueError("Blank journal entry path")
    p=PurePosixPath(relative)
    if p.is_absolute() or not p.parts or p.parts[0] not in ALLOW_ROOT:
        raise ValueError(f"Unsafe journal destination: {relative}")
    if ".." in p.parts or "." in p.parts or "\\" in relative:
        raise ValueError(f"Unsafe journal traversal: {relative}")
    return Path(*p.parts)


def _no_symlinks(root:Path,relative:Path)->None:
    if root.is_symlink():
        raise ValueError("Target root symlink not allowed")
    cursor=root
    for component in relative.parts:
        cursor=cursor/component
        if cursor.is_symlink():
            raise ValueError(f"Symlink in publish path: {cursor}")


@contextlib.contextmanager
def exclusive_lock(root:Path):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    fd=os.open(root/LOCK,os.O_RDWR|os.O_CREAT,0o600)
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("ARCHIVE_SYNC_CONCURRENT_WRITER_BLOCKED") from exc
        yield
    finally:
        try:
            fcntl.flock(fd,fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _read_manifest(journal:Path)->dict:
    path=journal/MANIFEST
    if not path.is_file():
        raise RuntimeError("INCOMPLETE_ARCHIVE_SYNC_JOURNAL_REQUIRES_MANUAL_REVIEW")
    m=json.loads(path.read_text(encoding="utf-8"))
    if m.get("schema")!="integrated-sync-journal/1" or not isinstance(m.get("files"),list):
        raise RuntimeError("UNRECOGNIZED_ARCHIVE_SYNC_JOURNAL")
    seen=set()
    for e in m["files"]:
        rel=_safe_relative(e.get("path"))
        if rel.as_posix() in seen:
            raise RuntimeError("DUPLICATE_ARCHIVE_SYNC_JOURNAL_ENTRY")
        seen.add(rel.as_posix())
        if not isinstance(e.get("old_exists"),bool):
            raise RuntimeError("MALFORMED_ARCHIVE_SYNC_JOURNAL")
        if not isinstance(e.get("new_sha256"),str) or len(e["new_sha256"])!=64:
            raise RuntimeError("MALFORMED_ARCHIVE_SYNC_JOURNAL")
        if e["old_exists"] and (not isinstance(e.get("old_sha256"),str) or len(e["old_sha256"])!=64):
            raise RuntimeError("MALFORMED_ARCHIVE_SYNC_JOURNAL")
    return m


def _verify_journal_payload(journal:Path,m:dict)->None:
    for item in m["files"]:
        rel=_safe_relative(item["path"])
        new=journal/"new"/rel
        if not new.is_file() or sha(new)!=item["new_sha256"]:
            raise RuntimeError(f"ARCHIVE_SYNC_JOURNAL_NEW_BYTES_MISSING_OR_CORRUPT: {rel}")
        if item["old_exists"]:
            old=journal/"old"/rel
            if not old.is_file() or sha(old)!=item["old_sha256"]:
                raise RuntimeError(f"ARCHIVE_SYNC_JOURNAL_BACKUP_MISSING_OR_CORRUPT: {rel}")


def _rollback(journal:Path,root:Path,m:dict)->None:
    # Verify *all* backups before modifying any destination.
    _verify_journal_payload(journal,m)
    for item in reversed(m["files"]):
        rel=_safe_relative(item["path"])
        _no_symlinks(root,rel)
        dest=root/rel
        if item["old_exists"]:
            _atomic_install(journal/"old"/rel,dest)
            if sha(dest)!=item["old_sha256"]:
                raise RuntimeError(f"ROLLBACK_CHECKSUM_FAILED: {rel}")
        elif dest.exists():
            if not dest.is_file():
                raise RuntimeError(f"ROLLBACK_UNEXPECTED_NONFILE: {rel}")
            dest.unlink()
            fsync_dir(dest.parent)


def _discard_resolved_journal(journal:Path,root:Path)->None:
    """Rename the *resolved* journal before recursively deleting it.

    If SIGKILL interrupts recursive cleanup, no active JOURNAL is left to be
    misinterpreted as an incomplete/unsafe recovery. Completed or rolled-back
    bytes have already been fsynced prior to this call.
    """
    target=root/(".integrated-sync-resolved-"+uuid.uuid4().hex)
    if target.exists():
        raise RuntimeError("ARCHIVE_SYNC_JOURNAL_RESOLVED_NAME_COLLISION")
    os.replace(journal,target)
    fsync_dir(root)
    shutil.rmtree(target)
    fsync_dir(root)


def recover_pending(root:Path)->dict:
    """Call under exclusive_lock; idempotent after SIGKILL/power interruption.

    No journal => unchanged. Draft preparation remnants don't affect canonical
    data, and are left for explicit cleanup rather than deleted blindly.
    """
    root=Path(root)
    journal=root/JOURNAL
    if not journal.exists():
        return {"status":"clean","journal_found":False}
    if not journal.is_dir() or journal.is_symlink():
        raise RuntimeError("ARCHIVE_SYNC_JOURNAL_NOT_DIRECTORY")
    m=_read_manifest(journal)
    _verify_journal_payload(journal,m)
    if (journal/COMMITTED).is_file():
        for item in m["files"]:
            rel=_safe_relative(item["path"])
            _no_symlinks(root,rel)
            dst=root/rel
            if not dst.is_file() or sha(dst)!=item["new_sha256"]:
                raise RuntimeError("COMMITTED_ARCHIVE_SYNC_DESTINATION_MISMATCH: "+str(rel))
        action="finished_committed"
    else:
        _rollback(journal,root,m)
        action="rolled_back_uncommitted"
    _discard_resolved_journal(journal,root)
    return {"status":action,"journal_found":True,"files":len(m["files"])}


def publish_staged_snapshot(stage:Path,root:Path,on_phase:Callable[[str,int],None]|None=None)->dict:
    """Publish from validated stage. Caller must hold exclusive_lock.

    Crash simulator callback exists only for offline fixture tests; it can
    terminate the process after each deterministic journal/publish phase.
    """
    stage,root=Path(stage),Path(root)
    if root/JOURNAL in stage.parents or (root/JOURNAL).exists():
        raise RuntimeError("PENDING_ARCHIVE_SYNC_JOURNAL_RECOVERY_REQUIRED")
    if not root.is_dir() or not stage.is_dir() or stage.resolve()==root.resolve():
        raise ValueError("Expected separate existing stage and target")
    files=sorted((p.relative_to(stage) for p in stage.rglob("*") if p.is_file()),
                 key=lambda p:p.as_posix())
    changes=[]
    for rel in files:
        rel=_safe_relative(rel.as_posix())
        _no_symlinks(root,rel)
        src,dest=stage/rel,root/rel
        if not src.is_file() or src.is_symlink():
            raise RuntimeError("UNSAFE_STAGED_SOURCE")
        if dest.exists() and not dest.is_file():
            raise RuntimeError("NONFILE_ARCHIVE_TARGET")
        if not dest.is_file() or sha(src)!=sha(dest):
            changes.append(rel)
    if not changes:
        return {"status":"unchanged","changed_files":0}

    draft=Path(tempfile.mkdtemp(prefix=DRAFT_PREFIX,dir=root))
    journal=root/JOURNAL
    sealed=False
    try:
        manifest={"schema":"integrated-sync-journal/1","files":[]}
        for rel in changes:
            dst=root/rel
            item={"path":rel.as_posix(),"old_exists":dst.is_file(),
                  "old_sha256":sha(dst) if dst.is_file() else None,
                  "new_sha256":sha(stage/rel)}
            for section,source in (("new",stage/rel),("old",dst)):
                if section=="old" and not item["old_exists"]:
                    continue
                stored=draft/section/rel
                stored.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,stored)
                with stored.open("rb") as fd:
                    os.fsync(fd.fileno())
                fsync_dir(stored.parent)
            manifest["files"].append(item)
        _write_json_atomic(draft/MANIFEST,manifest)
        _verify_journal_payload(draft,manifest)
        os.replace(draft,journal)
        sealed=True
        fsync_dir(root)
        if on_phase:
            on_phase("prepared",0)
        try:
            for i,item in enumerate(manifest["files"],1):
                rel=_safe_relative(item["path"])
                _no_symlinks(root,rel)
                _atomic_install(journal/"new"/rel,root/rel)
                if sha(root/rel)!=item["new_sha256"]:
                    raise RuntimeError("INSTALL_CHECKSUM_FAILED: "+str(rel))
                if on_phase:
                    on_phase("installed",i)
            _write_json_atomic(journal/COMMITTED,{"schema":"integrated-sync-journal-commit/1",
                                                  "files":len(manifest["files"])})
            fsync_dir(root)
            if on_phase:
                on_phase("committed",len(manifest["files"]))
        except BaseException as exc:
            if (journal/COMMITTED).exists():
                # Committed files remain authoritative. Retry cleanup on next
                # recovery; don't roll back an already durable commit marker.
                raise
            try:
                _rollback(journal,root,manifest)
                _discard_resolved_journal(journal,root)
            except BaseException as rollback_error:
                raise RuntimeError("ARCHIVE_SYNC_RECOVERY_REQUIRED: rollback failed") from rollback_error
            raise
        _discard_resolved_journal(journal,root)
        return {"status":"committed","changed_files":len(changes)}
    finally:
        if not sealed and draft.exists():
            shutil.rmtree(draft)
