"""Capture NEC name queries for two archived cross-council career cases."""
import gzip
import json
import platform
import time
from urllib.parse import urlencode

from audit_nec_election_samples import build
from collect_nec_election_samples import verify_transport
from probe_nec_election_sources import ROOT, URL, fetch
from process_meeting_segments import sha, write_json

COLLECTION = 'reports/nec-legacy-bridge-collection-latest.json'
AUDIT = 'reports/nec-legacy-bridge-audit-latest.json'
NAMES = ('육미선', '박정희')


def collect():
    if platform.system() != 'Darwin':
        raise ValueError('Official source requests require macOS')
    verify_transport(ROOT)
    groups = json.loads((ROOT / 'reports/cross-scope-identity-review-latest.json').read_text())['groups']
    eligible = {g['normalized_name'] for g in groups if g['legacy_to_integrated_review']}
    if not set(NAMES) <= eligible:
        raise ValueError('Missing archived cross-council review group')
    sources, errors = [], []
    for index, name in enumerate(NAMES):
        if index:
            time.sleep(1)
        url = URL + '?' + urlencode({'searchKeyword': name})
        try:
            raw = fetch(url)
            digest = sha(raw)
            relative = f'archive/elections/nec/source_responses/{digest}.txt.gz'
            path = ROOT / relative
            if path.exists() and gzip.decompress(path.read_bytes()) != raw:
                raise ValueError('Existing source hash mismatch')
            if not path.exists():
                path.write_bytes(gzip.compress(raw, mtime=0))
            sources.append({'query_name': name, 'url': url, 'method': 'GET',
                            'path': relative, 'sha256': digest, 'bytes': len(raw)})
        except Exception as exc:
            errors.append({'query_name': name, 'error': str(exc)[:200]})
    write_json(ROOT / COLLECTION, {
        'schema': 'cheongju-nec-election-samples/1', 'sources': sources,
        'status': 'SAMPLES_CAPTURED_FOR_OFFLINE_REVIEW' if not errors else 'PARTIAL',
        'target_profiles': len(NAMES), 'errors': errors,
    })
    audit = build(collection_relative=COLLECTION, output_relative=AUDIT, isolate_parse_errors=True)
    return bool(errors or audit['held_sources'])


if __name__ == '__main__':
    raise SystemExit(collect())
