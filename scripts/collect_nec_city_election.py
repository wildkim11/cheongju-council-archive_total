"""Bounded 2026 Cheongju four-committee / observed district snapshot.

Validate every district against its committee's actual select options before
report POSTs. Reuse verified sample/cache bytes; no schedule or identity merge.
"""
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import platform
import time
from urllib.parse import parse_qs, urlsplit

from audit_nec_election_samples import DOM, find, visible, sha
from build_nec_election_ledger import build as ledger
from collect_nec_report_samples import URL, plans as sample_plans, post_report
from probe_nec_detail_sources import detail_url, transport_evidence, inventory
from probe_nec_election_sources import ROOT, fetch
from process_meeting_segments import encoded, write_json

REPORT = 'reports/nec-city-election-collection-latest.json'
COMMITTEES = {'청주시상당구', '청주시서원구', '청주시흥덕구', '청주시청원구'}


def read_source(root, source):
    root = Path(root); p = (root / source['path']).resolve()
    if not any(p.is_relative_to((root / 'archive/elections/nec' / folder).resolve()) for folder in ('detail_responses','report_responses','city_responses')):
        raise ValueError('NEC city source path escape')
    raw = gzip.decompress(p.read_bytes())
    if sha(raw) != source['sha256'] or len(raw) != source['bytes']:
        raise ValueError('NEC city cached source hash/size mismatch')
    return raw


def select_options(text, name):
    dom = DOM(text); nodes = list(find(dom.root, lambda n: n['tag'] == 'select' and n['attrs'].get('id') == name))
    if len(nodes) != 1: raise ValueError('missing or duplicate NEC city selector')
    options = list(find(nodes[0], lambda n: n['tag'] == 'option'))
    values = [o['attrs'].get('value', '') for o in options]
    if len(set(values)) != len(values): raise ValueError('duplicate NEC selector values')
    return [{'value': o['attrs'].get('value', ''), 'label': visible(o), 'selected': 'selected' in o['attrs'],
             'char_start': o['start'], 'char_end': o['end'], 'span_sha256': sha(text[o['start']:o['end']].encode())} for o in options]


def initial_plan(root):
    root = Path(root)
    base = json.loads((root / 'reports/nec-detail-source-probe-latest.json').read_text())
    candidate_source = next(s for s in base['sources'] if s['menu_id'] == 'CPRI03')
    options = select_options(read_source(root, candidate_source).decode('utf-8-sig'), 'townCode')
    committees = {o['value']: o['label'] for o in options if o['label'] in COMMITTEES}
    if set(committees.values()) != COMMITTEES or len(committees) != 4:
        raise ValueError('official selector does not enumerate four Cheongju committees')
    evidence = ledger(root, write=False)
    districts, menus = {}, {}
    for r in evidence['rows']:
        if r['election_date'] != '2026-06-03' or r['codes']['election-code'] != '6': continue
        town, sgg = r['codes']['town-code'], r['codes']['sgg-town-code']
        if town not in committees: raise ValueError('observed Cheongju district outside official committees')
        key = (town, sgg)
        if key in districts and districts[key] != r['district_displayed']: raise ValueError('conflicting NEC district labels')
        districts[key] = r['district_displayed']
        for m in r['detail_menu_observations']:
            if m['menu_id'] == 'CPRI03':
                menus.setdefault(town, (m, r))
    if set(menus) != set(committees): raise ValueError('no observed candidate menu in every committee')
    targets = []
    for town in sorted(committees):
        menu, row = menus[town]
        raw = gzip.decompress((root / row['source_response_path']).read_bytes())
        if sha(raw) != row['source_response_sha256']: raise ValueError('city menu anchor hash mismatch')
        transport = transport_evidence(raw.decode('utf-8-sig'))
        url = candidate_source['url'] if town == '4301' else detail_url(menu)
        targets.append({'target_id': 'GET-CPRI03-' + town, 'method': 'GET', 'menu_id': 'CPRI03', 'url': url,
                        'town_code': town, 'committee': committees[town], 'inline_transport': transport,
                        'anchor_source_path': row['source_response_path'], 'anchor_source_sha256': row['source_response_sha256']})
    return committees, districts, targets


def verified_catalog(root, committees, observed, discovery):
    catalog = {}
    for source in discovery:
        text = read_source(root, source).decode('utf-8-sig')
        towns = select_options(text, 'townCode')
        selected = [o for o in towns if o['selected']]
        if not selected or selected[-1]['value'] != source['town_code']:
            raise ValueError('candidate discovery returned wrong committee')
        for option in select_options(text, 'sggTownCode'):
            if option['value'] == '0': continue
            key = (source['town_code'], option['value'])
            if observed.get(key) != option['label']: raise ValueError('official district selector and observed source coordinates disagree')
            if key in catalog: raise ValueError('duplicate discovered district')
            catalog[key] = {'district': option['label'], 'committee': committees[key[0]],
                            'selector_source_path': source['path'], 'selector_source_sha256': source['sha256'],
                            'selector_option': option}
    if set(catalog) != set(observed): raise ValueError('official district list incomplete against observed district coverage')
    return catalog


def report_plan(root, committees, catalog):
    templates = {r['menu_id']: r for r in sample_plans(root)}
    targets = []
    def target(menu, town, sgg=None):
        template = templates[menu]; change = {'townCode': town}
        if sgg is not None: change['sggTownCode'] = sgg
        pairs = [(k, change.get(k, v)) for k, v in template['form_pairs']]
        return {'target_id': 'POST-' + menu + '-' + town + ('-' + sgg if sgg else ''),
                'method': 'POST', 'url': URL, 'menu_id': menu, 'town_code': town,
                'committee': committees[town], 'district_code': sgg,
                'district': catalog[(town, sgg)]['district'] if sgg else None,
                'form_pairs': pairs, 'form_source_path': template['form_source_path'],
                'form_source_sha256': template['form_source_sha256'],
                'statement_selector': template['statement_selector'], 'selector_overrides': change,
                'district_selector_evidence': catalog[(town,sgg)] if sgg else None}
    for town in sorted(committees): targets.append(target('BIAP01', town))
    for town, sgg in sorted(catalog):
        for menu in ('CPRI03','VCCP08'): targets.append(target(menu, town, sgg))
    if len(targets) > 32: raise ValueError('city report snapshot exceeds reviewed request budget')
    return targets


def request_key(row):
    return sha(encoded([row['method'], row['url'], [list(p) for p in row.get('form_pairs', [])]]))


def collect(root=ROOT, *, get=fetch, post=post_report, system=platform.system, pause=time.sleep):
    if system() != 'Darwin': raise ValueError('official NEC city requests require macOS')
    root = Path(root); committees, observed, discovery_targets = initial_plan(root)
    old = json.loads((root / REPORT).read_text()) if (root / REPORT).exists() else {}
    cached = list(old.get('sources', []))
    for filename in ('nec-detail-source-probe-latest.json','nec-report-samples-latest.json'):
        cached.extend(json.loads((root / 'reports' / filename).read_text())['sources'])
    cache = {}
    for source in cached:
        read_source(root, source)  # Never silently refetch tampered archived bytes.
        cache[request_key(source)] = source
    sources, errors = [], []; requests = reused = 0
    report = {'schema': 'cheongju-nec-city-election-collection/1', 'status': 'INCOMPLETE',
              'maximum_requests': 36, 'attempts_per_request': 1, 'sources': sources, 'errors': errors,
              'committee_count': len(committees), 'observed_district_count': len(observed),
              'whole_city_results_verified': False, 'identity_merges': 0}
    def checkpoint():
        report.update(requests_this_run=requests, reused_verified_sources=reused)
        write_json(root / REPORT, report)
    def capture(target):
        nonlocal requests, reused
        key = request_key(target)
        if key in cache:
            previous = cache[key]; raw = read_source(root, previous); reused += 1
            captured = previous.get('captured_at')
        else:
            if requests >= 36: raise ValueError('city source request budget exhausted')
            if requests: pause(1)
            requests += 1
            raw = get(target['url'], max_bytes=8*1024*1024) if target['method'] == 'GET' else post(target['url'], target['form_pairs'])
            captured = datetime.now(timezone.utc).isoformat()
        digest = sha(raw); relative = 'archive/elections/nec/city_responses/' + digest + '.txt.gz'
        if key in cache: relative = cache[key]['path']
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and gzip.decompress(path.read_bytes()) != raw: raise ValueError('city source SHA collision')
        if not path.exists(): path.write_bytes(gzip.compress(raw, mtime=0))
        source = {**target, 'path': relative, 'sha256': digest, 'bytes': len(raw),
                  'captured_at': captured, 'inventory': inventory(raw)}
        sources.append(source); checkpoint()
        return source
    remaining = list(discovery_targets)
    try:
        discovery = []
        for target in discovery_targets:
            discovery.append(capture(target)); remaining.pop(0)
        catalog = verified_catalog(root, committees, observed, discovery)
        report['catalog'] = [{'town_code': k[0], 'district_code': k[1], **v} for k,v in sorted(catalog.items())]
        remaining = report_plan(root, committees, catalog)
        for target in list(remaining):
            capture(target); remaining.pop(0)
        report['status'] = 'CITY_SNAPSHOT_CAPTURED_NOT_RESULT_VALIDATION'
    except Exception as exc:
        errors.append({'target_id': remaining[0]['target_id'] if remaining else None,
                       'error': type(exc).__name__ + ': ' + str(exc)[:250]})
    failed = {e['target_id'] for e in errors}
    report['unattempted_target_ids'] = [t['target_id'] for t in remaining if t['target_id'] not in failed]
    checkpoint()
    return report


if __name__ == '__main__':
    r = collect(); print(json.dumps({k:v for k,v in r.items() if k not in {'sources','catalog'}}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not r['errors'] else 1)
