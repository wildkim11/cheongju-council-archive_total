"""Six bounded official detail-page GETs, including early-voting locations.

Only the preserved 2026 municipal district-code-6 transport is supported.
Raw capture is not complete district extraction or a polling-place vote map.
"""
import gzip
import json
from pathlib import Path
import platform
import re
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from audit_nec_election_samples import DOM, find, visible, sha
from build_nec_election_ledger import build as ledger
from probe_nec_election_sources import fetch, ROOT
from process_meeting_segments import write_json

MENUS = ('CPRI03', 'VCCP09', 'EPEI01', 'BIAP01', 'VCAP02', 'VCCP08')
TRANSPORT_SHA = 'c6a0e3bbb199d742f6a7f616302fb905f74b7398bad48c76fc8e1c73663b47d1'
REPORT = 'reports/nec-detail-source-probe-latest.json'


def transport_evidence(text):
    if text.count('function fn_searchSelect(') != 1:
        raise ValueError('missing or ambiguous NEC detail transport')
    a = text.index('function fn_searchSelect(')
    b = text.index('/* 생년월일', a)
    digest = sha(text[a:b].encode())
    if digest != TRANSPORT_SHA:
        raise ValueError('NEC inline transport changed; review required')
    return {'char_start': a, 'char_end': b, 'span_sha256': digest}


def detail_url(menu):
    """Explicit narrow translation of SHA-pinned fn_urlParamMake branches."""
    u = urlsplit(menu['observed_url']); q = parse_qs(u.query)
    attrs = menu['enclosing_data_attributes']
    if (u.scheme != 'https' or u.netloc != 'info.nec.go.kr' or u.path != '/main/showDocument.xhtml'
            or u.fragment or menu['menu_id'] not in MENUS or menu['menu_id_discrepancy']
            or q.get('electionId') != ['0020260603'] or q.get('secondMenuId') != [menu['menu_id']]
            or attrs.get('data-election-code') != '6' or attrs.get('data-city-code') != '4300'
            or attrs.get('data-election-name') != '20260603'):
        raise ValueError('unsupported NEC detail transport scope')
    allowed = {'electionCode', 'cityCode', 'townCode', 'sggTownCode', 'dateCode', 'timeCode'}
    keys = menu['selector_names']
    if not keys or len(keys) != len(set(keys)) or not set(keys) <= allowed:
        raise ValueError('unsupported NEC detail selector')
    values = []
    for key in keys:
        attr = 'data-' + re.sub(r'([A-Z])', lambda m: '-' + m[1].lower(), key)
        value = attrs.get(attr, '')
        if not re.fullmatch(r'\d+', value):
            raise ValueError('missing numeric NEC detail selector')
        # All other pinned helper branches are outside this explicit scope:
        # municipal election-code 6, Chungbuk city-code 4300, selected six menus.
        values.append((key, value))
    return menu['observed_url'] + '&searchAction=true&' + urlencode(values)


def targets(root):
    root = Path(root); report = ledger(root, write=False)
    rows = [r for r in report['rows'] if r['election_date'] == '2026-06-03'
            and r['codes']['election-code'] == '6' and r['current_profile_id']]
    if not rows:
        raise ValueError('no source-corroborated 2026 municipal anchor')
    anchor = sorted(rows, key=lambda r: r['event_id'])[0]
    raw = gzip.decompress((root / anchor['source_response_path']).read_bytes())
    if sha(raw) != anchor['source_response_sha256']:
        raise ValueError('NEC detail anchor source hash mismatch')
    transport = transport_evidence(raw.decode('utf-8-sig'))
    result = []
    for menu_id in MENUS:
        matches = [m for m in anchor['detail_menu_observations'] if m['menu_id'] == menu_id]
        urls = {detail_url(m) for m in matches}
        if len(urls) != 1:
            raise ValueError('missing or conflicting NEC detail menu')
        result.append({'menu_id': menu_id, 'url': urls.pop(), 'method': 'GET',
            'menu_label': matches[0]['label'], 'anchor_event_id': anchor['event_id'],
            'anchor_source_path': anchor['source_response_path'],
            'anchor_source_sha256': anchor['source_response_sha256'],
            'inline_transport': transport,
            'menu_source_spans': [{k: m[k] for k in ('tab', 'char_start', 'char_end', 'span_sha256')} for m in matches]})
    return result


def inventory(raw):
    text = raw.decode('utf-8-sig')
    if '<html' not in text.lower():
        raise ValueError('NEC detail response is not HTML')
    dom = DOM(text)
    return {'titles': [visible(n) for n in find(dom.root, lambda n: n['tag'] == 'title')],
        'scripts': sorted({n['attrs']['src'] for n in find(dom.root, lambda n: n['tag'] == 'script' and 'src' in n['attrs'])}),
        'forms': [{k: n['attrs'].get(k) for k in ('id', 'name', 'method', 'action')}
                  for n in find(dom.root, lambda n: n['tag'] == 'form')],
        'table_count': sum(1 for _ in find(dom.root, lambda n: n['tag'] == 'table')),
        'selects': [{'id': n['attrs'].get('id'), 'name': n['attrs'].get('name'),
                    'options': [{'value': o['attrs'].get('value'), 'label': visible(o),
                                 'selected': 'selected' in o['attrs']}
                                for o in find(n, lambda n: n['tag'] == 'option')]}
                   for n in find(dom.root, lambda n: n['tag'] == 'select')],
        'result_extraction_verified': False}


def collect(root=ROOT, *, request=fetch, system=platform.system, pause=time.sleep):
    if system() != 'Darwin':
        raise ValueError('official NEC detail transport requires macOS')
    root = Path(root); planned = targets(root)
    previous = json.loads((root / REPORT).read_text()) if (root / REPORT).exists() else {}
    cache = {s['url']: s for s in previous.get('sources', [])}
    sources, errors, attempts, reused = [], [], 0, 0
    for target in planned:
        try:
            old = cache.get(target['url'])
            if old:
                p = (root / old['path']).resolve()
                if not p.is_relative_to((root / 'archive/elections/nec/detail_responses').resolve()):
                    raise ValueError('cached NEC detail source path escape')
                raw = gzip.decompress(p.read_bytes())
                if sha(raw) != old['sha256'] or len(raw) != old['bytes']:
                    raise ValueError('cached NEC detail source hash/size mismatch')
                reused += 1
            else:
                if attempts: pause(1)
                attempts += 1
                raw = request(target['url'], max_bytes=8 * 1024 * 1024)
            observed = inventory(raw); digest = sha(raw)
            relative = 'archive/elections/nec/detail_responses/' + digest + '.txt.gz'
            p = root / relative; p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists() and gzip.decompress(p.read_bytes()) != raw:
                raise ValueError('NEC detail content-addressed response mismatch')
            if not p.exists(): p.write_bytes(gzip.compress(raw, mtime=0))
            sources.append({**target, 'path': relative, 'sha256': digest, 'bytes': len(raw), 'inventory': observed})
        except Exception as exc:
            errors.append({'menu_id': target['menu_id'], 'url': target['url'], 'error': type(exc).__name__ + ': ' + str(exc)[:200]})
            break
    report = {'schema': 'cheongju-nec-detail-source-probe/1',
        'status': 'SIX_DETAIL_PAGES_CAPTURED_FOR_REVIEW' if len(sources) == 6 else 'INCOMPLETE',
        'maximum_requests': 6, 'attempts_per_request': 1, 'requests_this_run': attempts,
        'reused_verified_sources': reused, 'sources': sources, 'errors': errors,
        'unattempted_menu_ids': [t['menu_id'] for t in planned if t['url'] not in {s['url'] for s in sources} and t['url'] not in {e['url'] for e in errors}],
        'complete_district_results': False, 'polling_place_vote_geography_verified': False,
        'note': 'Bounded source inspection only. Table count or HTTP 200 does not verify actual results, full candidates, polling-place geography or vote denominators.'}
    write_json(root / REPORT, report)
    return report


if __name__ == '__main__':
    r = collect()
    print(json.dumps({k: v for k, v in r.items() if k != 'sources'}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if r['status'] == 'SIX_DETAIL_PAGES_CAPTURED_FOR_REVIEW' else 1)
