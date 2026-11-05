"""Three read-only report form samples from verified NEC detail originals."""
from datetime import datetime, timezone
import gzip
import http.client
import json
from pathlib import Path
import platform
import ssl
import time
from urllib.parse import urlencode, urljoin

from audit_nec_election_samples import DOM, find, sha
from probe_nec_detail_sources import ROOT, inventory
from process_meeting_segments import write_json

URL = 'https://info.nec.go.kr/electioninfo/electionInfo_report.xhtml'
MENUS = ('BIAP01', 'CPRI03', 'VCCP08')
STATEMENTS = {'CPRI03': ('CPRI03_#6', '6dfd86a2a2661662cdbfdd5742b12aab72195dbe5f8caf2ccd94044c0f79f92f'),
              'VCCP08': ('VCCP08_#00', 'e90e79679e6adb68e965ca93e31a8ad0cd940554387d1687bb34b9e5c8e43e72')}
REPORT = 'reports/nec-report-samples-latest.json'


def post_report(url, pairs):
    if url != URL:
        raise ValueError('unexpected NEC read-only report URL')
    body = urlencode(pairs).encode('ascii')
    conn = http.client.HTTPSConnection('info.nec.go.kr', timeout=25, context=ssl.create_default_context())
    try:
        conn.request('POST', '/electioninfo/electionInfo_report.xhtml', body=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'CheongjuCouncilArchive-ReportSample/0.1'})
        response = conn.getresponse(); raw = response.read(8 * 1024 * 1024 + 1)
        if response.status != 200 or len(raw) > 8 * 1024 * 1024:
            raise ValueError(f'NEC report HTTP {response.status}, bytes {len(raw)}')
        return raw
    finally:
        conn.close()


def statement_span(text, menu):
    if menu not in STATEMENTS:
        return None
    a = text.index('function chooseStatementId()'); start = text.index('{', a); depth = 0
    for b in range(start, len(text)):
        if text[b] == '{': depth += 1
        if text[b] == '}': depth -= 1
        if not depth:
            digest = sha(text[a:b+1].encode())
            if digest != STATEMENTS[menu][1]:
                raise ValueError('NEC report statement selector changed')
            return {'char_start': a, 'char_end': b+1, 'span_sha256': digest}
    raise ValueError('unclosed NEC statement selector')


def form_contract(text, menu):
    if menu not in MENUS:
        raise ValueError('unsupported NEC report sample menu')
    dom = DOM(text)
    forms = list(find(dom.root, lambda n: n['tag'] == 'form' and n['attrs'].get('id') == 'searchForm'))
    if len(forms) != 1:
        raise ValueError('missing or ambiguous NEC report search form')
    form = forms[0]
    if (urljoin('https://info.nec.go.kr/', form['attrs'].get('action', '')) != URL
            or form['attrs'].get('method', '').lower() != 'post' or form['end'] is None):
        raise ValueError('unexpected NEC report form destination/method')
    pairs, selector_notes = [], []
    for n in find(form, lambda n: n['tag'] in {'input', 'select'}):
        attrs = n['attrs']; name = attrs.get('name')
        if not name or 'disabled' in attrs: continue
        if n['tag'] == 'select':
            if 'multiple' in attrs: raise ValueError('unsupported multiple report selector')
            options = list(find(n, lambda n: n['tag'] == 'option'))
            selected = [o for o in options if 'selected' in o['attrs']]
            if not options: raise ValueError('empty report selector')
            # A single-select with multiple selected attributes uses the last
            # selected option on HTML initialization. Preserve the discrepancy.
            if len(selected) > 1:
                selector_notes.append({'name': name, 'selected_attribute_values': [o['attrs'].get('value') for o in selected],
                                       'rule': 'single_select_last_selected_attribute'})
            pairs.append((name, (selected[-1:] or options[:1])[0]['attrs'].get('value', '')))
        else:
            kind = attrs.get('type', 'text').lower()
            if kind in {'submit', 'button', 'reset', 'image'}: continue
            if kind in {'radio', 'checkbox'} and 'checked' not in attrs: continue
            if kind not in {'hidden', 'text', 'radio', 'checkbox'}: raise ValueError('unexpected report input type')
            pairs.append((name, attrs.get('value', '')))
    values = dict(pairs)
    if len(values) != len(pairs): raise ValueError('duplicate report field')
    if (values.get('electionId') != '0020260603' or values.get('menuId') != menu
            or values.get('secondMenuId') != menu
            or values.get('requestURI') != '/electioninfo/0020260603/' + menu[:2].lower() + '/' + menu.lower() + '.jsp'
            or values.get('cityCode') != '4300' or values.get('townCode') != '4301'):
        raise ValueError('unsupported NEC sample report scope')
    evidence = statement_span(text, menu)
    if menu in STATEMENTS:
        if values.get('electionCode') != '6': raise ValueError('unsupported report election kind')
        pairs = [(k, STATEMENTS[menu][0] if k == 'statementId' else v) for k, v in pairs]
    elif values.get('statementId') != 'BIAP01':
        raise ValueError('unexpected early-voting location statement')
    if 'statementId' not in values: raise ValueError('missing NEC report statement field')
    return {'menu_id': menu, 'url': URL, 'method': 'POST', 'form_pairs': pairs,
            'form_span': {'char_start': form['start'], 'char_end': form['end'],
                          'span_sha256': sha(text[form['start']:form['end']].encode())},
            'statement_selector': evidence, 'selector_notes': selector_notes}


def plans(root):
    root = Path(root); manifest = json.loads((root / 'reports/nec-detail-source-probe-latest.json').read_text())
    sources = {s['menu_id']: s for s in manifest['sources']}
    rows = []
    for menu in MENUS:
        source = sources[menu]; path = (root / source['path']).resolve()
        if not path.is_relative_to((root / 'archive/elections/nec/detail_responses').resolve()):
            raise ValueError('NEC detail form source path escape')
        raw = gzip.decompress(path.read_bytes())
        if sha(raw) != source['sha256'] or len(raw) != source['bytes']:
            raise ValueError('NEC form source hash/size mismatch')
        rows.append({**form_contract(raw.decode('utf-8-sig'), menu),
                     'form_source_path': source['path'], 'form_source_sha256': source['sha256']})
    return rows


def collect(root=ROOT, *, request=post_report, system=platform.system, pause=time.sleep):
    if system() != 'Darwin': raise ValueError('official report transport requires macOS')
    root = Path(root); planned = plans(root)
    sources, errors = [], []
    for target in planned:
        try:
            if sources: pause(1)
            raw = request(target['url'], target['form_pairs']); observed = inventory(raw)
            digest = sha(raw); relative = 'archive/elections/nec/report_responses/' + digest + '.txt.gz'
            p = root / relative; p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists() and gzip.decompress(p.read_bytes()) != raw: raise ValueError('report response SHA collision')
            if not p.exists(): p.write_bytes(gzip.compress(raw, mtime=0))
            sources.append({**target, 'path': relative, 'sha256': digest, 'bytes': len(raw),
                            'captured_at': datetime.now(timezone.utc).isoformat(), 'inventory': observed})
        except Exception as exc:
            errors.append({'menu_id': target['menu_id'], 'error': type(exc).__name__ + ': ' + str(exc)[:200]}); break
    report = {'schema': 'cheongju-nec-report-samples/1', 'status': 'REPORT_SAMPLES_CAPTURED' if len(sources) == 3 else 'INCOMPLETE',
        'maximum_requests': 3, 'attempts_per_request': 1, 'sources': sources, 'errors': errors,
        'unattempted_menu_ids': [p['menu_id'] for p in planned if p['menu_id'] not in {s['menu_id'] for s in sources} | {e['menu_id'] for e in errors}],
        'complete_district_results': False, 'polling_place_result_links_verified': False}
    write_json(root / REPORT, report)
    return report


if __name__ == '__main__':
    r = collect(); print(json.dumps({k: v for k, v in r.items() if k != 'sources'}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if r['status'] == 'REPORT_SAMPLES_CAPTURED' else 1)
