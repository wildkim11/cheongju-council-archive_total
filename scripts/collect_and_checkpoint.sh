#!/usr/bin/env bash
# Every family is a separately validated, durable Git checkpoint.
set -euo pipefail
requested="${1:-auto}"
if [ "$requested" = 'all' ]; then
  families='minutes bills activities people groups media attachments'
elif [ "$requested" = 'bootstrap' ]; then
  families="$(python - <<'PY'
import datetime as dt,json
from pathlib import Path
p=Path('reports/automatic/collection_state.json');state=json.loads(p.read_text()) if p.exists() else {};now=dt.datetime.now(dt.timezone.utc);needed=[]
for family in ('minutes','bills','activities','people','groups','media','attachments'):
    slot=state.get('families',{}).get(family,{});stamp=slot.get('last_success_at');recent=False
    if stamp:
        recent=slot.get('consecutive_failures',0)==0 and now-dt.datetime.fromisoformat(stamp)<dt.timedelta(hours=24)
    if not recent:needed.append(family)
print(' '.join(needed))
PY
)"
else
  families="$requested"
fi
failed=0
git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
for family in $families; do
  if ! python -u scripts/automated_collection.py --family "$family" ${EXPLICIT_RETRY:-}; then
    failed=1
  fi
  git add archive indexes exports reports
  if ! git diff --cached --quiet; then
    git commit -m "data: automatic $family collection checkpoint"
    bash scripts/push_collected_snapshot.sh
  fi
done
exit "$failed"
