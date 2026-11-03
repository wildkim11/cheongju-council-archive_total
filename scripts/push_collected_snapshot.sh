#!/usr/bin/env bash
# Allow concurrent code-only changes; never merge two independently collected snapshots.
set -euo pipefail
branch="${1:-feature/archive-foundation}"
git fetch origin "$branch"
if ! git merge-base --is-ancestor "origin/$branch" HEAD; then
  # HEAD is the newly created data commit; HEAD~1 is its collection baseline.
  git diff --name-only HEAD~1 "origin/$branch" | python -c '
import sys
paths=[p.strip() for p in sys.stdin if p.strip()]
if not all(p.startswith(("scripts/","tests/","docs/",".github/")) for p in paths):
    raise SystemExit("REMOTE_SOURCE_SNAPSHOT_CHANGED: recollect instead of overwriting another snapshot")
'
  git rebase "origin/$branch"
  python -m unittest discover -s tests
  python scripts/validate_archive.py
  python scripts/audit_stage_c.py --output "${TMPDIR:-/tmp}/after-collection-rebase.json"
fi
git push origin "HEAD:$branch"
