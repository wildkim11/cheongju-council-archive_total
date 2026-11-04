"""Collect three bounded public NEC name-search samples after source inspection."""
import gzip
import hashlib
import json
from pathlib import Path
import platform
import time
from urllib.parse import urlencode

from probe_nec_election_sources import ROOT, URL, fetch

TARGETS = [('person-fcode-2130', '최동식'), ('person-fcode-1120', '남일현'), ('person-fcode-10040', '김완식')]


def collect(root=ROOT, *, request=fetch, system=platform.system):
    if system() != 'Darwin':
        raise ValueError('official election requests require macOS')
    root = Path(root)
    inspection = json.loads((root / 'reports/nec-source-inspection-latest.json').read_text())
    transport_verified = False
    for source in inspection['sources']:
        if source['url'] != 'https://info.nec.go.kr/common/js/search.js?ver=231025':
            continue
        path = (root / source['path']).resolve()
        if not path.is_relative_to((root / 'archive/elections/nec/source_responses').resolve()):
            raise ValueError('NEC inspected source path escape')
        raw = gzip.decompress(path.read_bytes())
        if hashlib.sha256(raw).hexdigest() != source['sha256'] or len(raw) != source['bytes']:
            raise ValueError('NEC inspected source hash mismatch')
        text = raw.decode('utf-8-sig')
        transport_verified = '/search/searchCandidate.xhtml?searchKeyword=' in text and 'encodeURIComponent(searchKeyword)' in text
    if not transport_verified:
        raise ValueError('public name-search GET transport not confirmed from captured official JS')
    careers = json.loads((root / 'reports/current-career-evidence-latest.json').read_text())
    known = {(r['profile_id'], r['name']) for r in careers['rows']}
    if not set(TARGETS).issubset(known):
        raise ValueError('sample target differs from preserved current career profile')
    sources, errors = [], []
    for index, (pid, name) in enumerate(TARGETS):
        url = URL + '?' + urlencode({'searchKeyword': name})
        try:
            raw = request(url)
            if '<html' not in raw.decode('utf-8-sig').lower():
                raise ValueError('NEC sample is not HTML')
            digest = hashlib.sha256(raw).hexdigest()
            relative = 'archive/elections/nec/source_responses/' + digest + '.txt.gz'
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and gzip.decompress(path.read_bytes()) != raw:
                raise ValueError('NEC sample content-addressed response mismatch')
            if not path.exists(): path.write_bytes(gzip.compress(raw, mtime=0))
            sources.append({'current_profile_id': pid, 'query_name': name, 'url': url,
                            'method': 'GET', 'path': relative, 'sha256': digest, 'bytes': len(raw)})
            if index < len(TARGETS)-1: time.sleep(1)
        except Exception as exc:
            errors.append({'url': url, 'error': type(exc).__name__ + ': ' + str(exc)[:200]})
            break
    report = {'schema': 'cheongju-nec-election-samples/1',
        'status': 'SAMPLES_CAPTURED_FOR_OFFLINE_REVIEW' if len(sources) == 3 else 'INCOMPLETE',
        'sources': sources, 'errors': errors, 'maximum_requests': 3, 'attempts_per_request': 1,
        'seniority_decisions': 0, 'identity_merges': 0,
        'note': 'A name search can include homonyms, candidates and winners. No row is a confirmed current-person election until offline type and identity checks.'}
    output = root / 'reports/nec-election-sample-collection-latest.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    result = collect(); print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'SAMPLES_CAPTURED_FOR_OFFLINE_REVIEW' else 1)
