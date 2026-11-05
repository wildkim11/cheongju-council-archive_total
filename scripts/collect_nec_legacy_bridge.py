"""Capture NEC name queries for all archived cross-council review names."""
import gzip
import json
import platform
import re
import time
from urllib.parse import urlencode

from audit_nec_election_samples import build
from collect_nec_current_roster import LIMIT, verify_source
from collect_nec_election_samples import verify_transport
from probe_nec_election_sources import ROOT, URL, fetch
from process_meeting_segments import sha, write_json

COLLECTION = 'reports/nec-legacy-bridge-collection-latest.json'
AUDIT = 'reports/nec-legacy-bridge-audit-latest.json'
CACHE_REPORTS = (
    COLLECTION,
    'reports/nec-current-roster-collection-latest.json',
    'reports/nec-election-sample-collection-latest.json',
)


def collect():
    if platform.system() != 'Darwin':
        raise ValueError('Official source requests require macOS')
    verify_transport(ROOT)
    groups = json.loads((ROOT / 'reports/cross-scope-identity-review-latest.json').read_text())['groups']
    names = sorted({g['normalized_name'] for g in groups if g['legacy_to_integrated_review']})
    if not names or any(not re.fullmatch(r'[가-힣]{2,5}', name) for name in names):
        raise ValueError('Invalid archived cross-council review names')
    cached = {}
    for relative in CACHE_REPORTS:
        path = ROOT / relative
        if path.is_file():
            for source in json.loads(path.read_text())['sources']:
                if source['query_name'] in names:
                    cached.setdefault(source['query_name'], []).append(source)

    sources, errors = [], []
    for name in names:
        for source in cached.get(name, []):
            try:
                verify_source(ROOT, source)
            except (KeyError, OSError, ValueError):
                continue
            sources.append({**source, 'reused_preserved_source': True})
            break
        else:
            url = URL + '?' + urlencode({'searchKeyword': name})
            try:
                time.sleep(1)
                raw = fetch(url, max_bytes=LIMIT)
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
        'target_profiles': len(names), 'errors': errors,
    })
    audit = build(collection_relative=COLLECTION, output_relative=AUDIT, isolate_parse_errors=True)
    return bool(errors or audit['held_sources'])


if __name__ == '__main__':
    raise SystemExit(collect())
