#!/usr/bin/env bash
# Allow concurrent code-only changes; never merge two independently collected snapshots.
set -euo pipefail
branch="${1:-feature/archive-foundation}"
git fetch origin "$branch"
if ! git merge-base --is-ancestor "origin/$branch" HEAD; then
  # HEAD is the newly created data commit; HEAD~1 is its collection baseline.
  python scripts/validate_collection_rebase.py "origin/$branch"
  git rebase "origin/$branch"
  python -m unittest discover -s tests
  python scripts/validate_archive.py
  python scripts/audit_stage_c.py --output "${TMPDIR:-/tmp}/after-collection-rebase.json"
  if [ -f exports/processing/manifest.json ]; then
    python scripts/verify_processing.py
  fi
  if [ -f reports/written-question-link-audit.json ]; then
    python scripts/audit_written_question_links.py --strict
  fi
  # A validator must not silently leave a different tracked snapshot uncommitted.
  git diff --quiet && git diff --cached --quiet
fi
git push origin "HEAD:$branch"
