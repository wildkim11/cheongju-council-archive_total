"""Bounded macOS collection of three observed official navigation targets.

Preserves source bytes for offline period review. Never infers dates, promotes
periods, merges identities, or modifies existing activity/analyzer datasets.
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import http.client
import json
from pathlib import Path
import platform
import ssl
import time

ROOT = Path(__file__).resolve().parents[1]
HOST = 'council.cheongju.go.kr'
TARGETS = (
    '/content/council/history.html',
    '/content/member/memberMission.html',
    '/content/council/configuration.html',
)
LIMIT = 2 * 1024 * 1024


def request(target):
    if target not in TARGETS:
        raise ValueError('unobserved source target')
    connection = http.client.HTTPSConnection(HOST, timeout=30, context=ssl.create_default_context())
    try:
        connection.request('GET', target, headers={'User-Agent': 'CheongjuCouncilArchive/0.1'})
        response = connection.getresponse()
        raw = response.read(LIMIT + 1)
        if response.status != 200 or len(raw) > LIMIT:
            raise ValueError(f'invalid response: HTTP {response.status}, bytes {len(raw)}')
        text = raw.decode('utf-8-sig')
        if '<html' not in text.lower():
            raise ValueError('not an HTML response')
        return text
    finally:
        connection.close()


def collect(root=ROOT, *, fetch=request, system=platform.system):
    if system() != 'Darwin':
        raise ValueError('official source requests require macOS')
    root = Path(root)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    responses, failures = [], []
    for target in TARGETS:
        try:
            raw = fetch(target).encode('utf-8')
            digest = hashlib.sha256(raw).hexdigest()
            relative = Path('archive/source_responses') / (digest + '.html.gz')
            path = root / relative
            if path.exists():
                if gzip.decompress(path.read_bytes()) != raw:
                    raise ValueError('existing content-addressed response mismatch')
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(gzip.compress(raw, mtime=0))
            responses.append({'url': 'https://' + HOST + target,
                'path': str(relative), 'decoded_utf8_sha256': digest, 'bytes': len(raw),
                'request_parameters_sha256': hashlib.sha256(b'null').hexdigest()})
        except Exception as exc:
            failures.append({'url': 'https://' + HOST + target,
                             'error': type(exc).__name__ + ': ' + str(exc)[:200]})
            break
        if target != TARGETS[-1]:
            time.sleep(1)
    document = {'schema': 'cheongju-source-responses/1', 'family': 'council_period_sources',
                'collection_started_at': started, 'responses': responses}
    encoded = (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    relative = Path('archive/source_responses/manifests') / (hashlib.sha256(encoded).hexdigest() + '.json')
    (root / relative).parent.mkdir(parents=True, exist_ok=True)
    (root / relative).write_bytes(encoded)
    report = {'schema': 'cheongju-council-period-source-collection/1',
        'status': 'CAPTURED_FOR_REVIEW' if len(responses) == len(TARGETS) else 'INCOMPLETE',
        'source_manifest': str(relative), 'responses': len(responses), 'failures': failures,
        'maximum_requests': 3, 'attempts_per_request': 1, 'runtime_platform': system(),
        'official_periods_promoted': 0, 'identities_merged': 0}
    output = root / 'reports/council-period-source-collection-latest.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    result = collect()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'CAPTURED_FOR_REVIEW' else 1)
