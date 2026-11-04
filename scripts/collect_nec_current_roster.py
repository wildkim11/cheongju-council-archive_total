"""Bounded incremental NEC name-query snapshot for the preserved current roster."""
import datetime as dt
import gzip
import json
from pathlib import Path
import platform
import re
import time
from urllib.parse import urlencode, urlsplit, parse_qs

from probe_nec_election_sources import ROOT, URL, fetch
from collect_nec_election_samples import verify_transport
from build_current_career_evidence import build as career_evidence
from build_career_roster_crosswalk import current_rosters
from process_meeting_segments import encoded, sha

LIMIT = 8 * 1024 * 1024
OUTPUT = 'reports/nec-current-roster-collection-latest.json'


def verify_source(root, source):
    u = urlsplit(source['url'])
    if (u.scheme != 'https' or u.netloc != 'info.nec.go.kr' or u.path != '/search/searchCandidate.xhtml'
            or parse_qs(u.query) != {'searchKeyword': [source['query_name']]} or source['method'] != 'GET'):
        raise ValueError('NEC cached query mismatch')
    path = (root / source['path']).resolve()
    if not path.is_relative_to((root / 'archive/elections/nec/source_responses').resolve()):
        raise ValueError('NEC cached source path escape')
    raw = gzip.decompress(path.read_bytes())
    if sha(raw) != source['sha256'] or len(raw) != source['bytes'] or len(raw) > LIMIT:
        raise ValueError('NEC cached source bytes mismatch')
    return raw


def collect(root=ROOT, *, request=None, system=platform.system):
    if system() != 'Darwin': raise ValueError('official election requests require macOS')
    root = Path(root)
    verify_transport(root)
    careers = career_evidence(root, write=False)
    roster = current_rosters(root)
    targets = sorted({(r['profile_id'], r['name'], r['source_url']) for r in careers['rows']})
    if len(targets) != 44 or len({name for _, name, _ in targets}) != 44:
        raise ValueError('expected 44 distinct source-backed current profile names')
    if any(not roster.get((name, profile_url)) or not re.fullmatch(r'[가-힣]{2,5}', name) for _, name, profile_url in targets):
        raise ValueError('current election query target lacks preserved current roster evidence')
    request = request or (lambda url: fetch(url, max_bytes=LIMIT))
    cached = {}
    for relative in ('reports/nec-election-sample-collection-latest.json', OUTPUT):
        path = root / relative
        if not path.exists(): continue
        doc = json.loads(path.read_text())
        if doc.get('schema') not in {'cheongju-nec-election-samples/1', 'cheongju-nec-current-roster-collection/1'}:
            raise ValueError('invalid prior NEC collection schema')
        for source in doc['sources']:
            verify_source(root, source)
            cached[source['current_profile_id'], source['query_name']] = source
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    sources, errors, unattempted = [], [], []
    attempts = consecutive_errors = 0
    for index, (pid, name, _) in enumerate(targets):
        if (pid, name) in cached:
            sources.append({**cached[pid, name], 'reused_preserved_source': True})
            continue
        if consecutive_errors >= 3:
            unattempted.append({'current_profile_id': pid, 'query_name': name, 'reason': 'stopped_after_three_consecutive_source_errors'})
            continue
        url = URL + '?' + urlencode({'searchKeyword': name})
        attempts += 1
        try:
            raw = request(url)
            if len(raw) > LIMIT or '<html' not in raw.decode('utf-8-sig').lower():
                raise ValueError('NEC current-roster response format or size invalid')
            digest = sha(raw); relative = 'archive/elections/nec/source_responses/' + digest + '.txt.gz'
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and gzip.decompress(path.read_bytes()) != raw:
                raise ValueError('NEC content-addressed current-roster response mismatch')
            if not path.exists(): path.write_bytes(gzip.compress(raw, mtime=0))
            sources.append({'current_profile_id': pid, 'query_name': name, 'url': url, 'method': 'GET',
                'path': relative, 'sha256': digest, 'bytes': len(raw),
                'collected_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'reused_preserved_source': False})
            consecutive_errors = 0
        except Exception as exc:
            errors.append({'current_profile_id': pid, 'query_name': name, 'url': url,
                           'error': type(exc).__name__ + ': ' + str(exc)[:200]})
            consecutive_errors += 1
        if index < len(targets)-1: time.sleep(1)
    report = {'schema': 'cheongju-nec-current-roster-collection/1',
        'status': 'ROSTER_SEARCHES_CAPTURED' if len(sources) == len(targets) else 'PARTIAL',
        'collection_started_at_utc': started, 'target_profiles': len(targets),
        'career_evidence_sha256': sha(encoded(careers)), 'sources': sources, 'errors': errors,
        'unattempted_profiles': unattempted, 'official_requests_attempted': attempts,
        'reused_preserved_sources': sum(s['reused_preserved_source'] for s in sources),
        'maximum_requests': 44, 'maximum_response_bytes': LIMIT, 'attempts_per_request': 1,
        'runtime_platform': system(), 'identity_merges': 0, 'seniority_decisions': 0,
        'note': 'Incremental bounded roster snapshot, not a scheduled refresh. Three-error circuit stop. Queries are targets only, not confirmed person identities or complete election histories.'}
    output = root / OUTPUT; output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    result = collect(); print(json.dumps({k: v for k, v in result.items() if k != 'sources'}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'ROSTER_SEARCHES_CAPTURED' else 1)
