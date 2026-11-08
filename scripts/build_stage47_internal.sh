#!/usr/bin/env bash
# Run against a local checkout of the collected archive. Keep the master local.
set -euo pipefail

if [[ $# != 3 ]]; then
  echo "Usage: bash build_stage47_internal.sh MASTER.html ARCHIVE_CHECKOUT NEW_OUTPUT_DIR" >&2
  exit 2
fi

scripts="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
master="$1"
archive="$2"
out="$3"
if [[ -n "$(git -C "$archive" status --porcelain --untracked-files=all -- exports/analyzer)" ]]; then
  echo "Use committed analyzer exports from the collection checkpoint." >&2
  exit 1
fi
commit="$(git -C "$archive" rev-parse HEAD)"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
python3 "$scripts/build_stage47_candidate.py" "$master" "$archive/exports/analyzer" \
  "$commit" "$work/candidate.json"
node "$scripts/package_stage47_release.cjs" "$master" "$work/candidate.json" "$out"
