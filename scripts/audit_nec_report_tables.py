"""Source-coordinate facility, candidate and count-unit sample ledgers.

No name-only member joins, seat/rank/margin inference or physical polling-place
assignment to out-of-area ballots. Samples cover one committee/district only.
"""
import gzip
import json
from pathlib import Path
import re

from audit_nec_election_samples import DOM, find, visible, sha
from collect_nec_report_samples import ROOT, URL, MENUS, plans
from process_meeting_segments import write_json


def cells(row):
    return [n for n in row['children'] if isinstance(n, dict) and n['tag'] in {'td', 'th'}]


def evidence(text, node):
    if node['end'] is None: raise ValueError('unclosed NEC report source range')
    return {'char_start': node['start'], 'char_end': node['end'],
            'span_sha256': sha(text[node['start']:node['end']].encode())}


def table_rows(text):
    dom = DOM(text)
    tables = list(find(dom.root, lambda n: n['tag'] == 'table' and n['attrs'].get('id') == 'table01'))
    if len(tables) != 1: raise ValueError('missing or duplicate NEC report table01')
    return tables[0], list(find(tables[0], lambda n: n['tag'] == 'tr'))


def facilities(text):
    table, rows = table_rows(text)
    expected = ['구시군명', '읍면동명', '사전투표소명', '설치장소(건물명)', '소재지', '장애인 편의시설', '임시기표소 설치대상']
    if [visible(c) for c in cells(rows[0])] != expected: raise ValueError('early-voting facility headers changed')
    result = []
    for tr in rows[1:]:
        cs = cells(tr)
        if len(cs) != 7 or any(c['tag'] != 'td' or c['attrs'].get('rowspan', '1') != '1' or c['attrs'].get('colspan', '1') != '1' for c in cs):
            raise ValueError('unsupported facility table row')
        labels = [visible(c) for c in cs]
        if labels[0] != '청주시상당구' or not all(labels[i] for i in (1,2,3,4)):
            raise ValueError('missing or unexpected facility scope')
        result.append({'election_id': '0020260603', 'committee_displayed': labels[0],
            'ward_displayed': labels[1], 'polling_place_name': labels[2],
            'building_floor_room_displayed': labels[3], 'address_displayed': labels[4],
            'accessibility_text': labels[5],
            'accessibility_image_labels': [n['attrs'].get('alt', '') for n in find(cs[5], lambda n: n['tag'] == 'img')],
            'temporary_booth_target_displayed': labels[6], 'official_polling_place_id': None,
            'coordinates': None, 'operating_dates_verified': False, 'candidate_vote_link_verified': False,
            'source_row': evidence(text, tr)})
    return result, evidence(text, table)


def candidates(text):
    table, rows = table_rows(text)
    header = [visible(c) for c in cells(rows[0])]
    if header != ['선거구명', '사진', '기호', '소속 정당명', '성명 (한자)', '성별', '생년월일 (연령)', '주소', '직업', '학력', '경력']:
        raise ValueError('candidate headers changed')
    result = []
    for tr in rows[1:]:
        cs = cells(tr)
        if len(cs) != 11 or any(c['tag'] != 'td' for c in cs): raise ValueError('unsupported candidate row')
        name = re.fullmatch(r'([가-힣]+)\s*\([^()]+\)', visible(cs[4]))
        if visible(cs[0]) != '청주시나선거구' or not name: raise ValueError('candidate district/name shape changed')
        result.append({'district_displayed': visible(cs[0]), 'ballot_label': visible(cs[2]),
            'party_at_election': visible(cs[3]), 'name': name[1], 'current_profile_id': None,
            'source_row': evidence(text, tr), 'selected_cell_evidence': {
                k: evidence(text, cs[i]) for k, i in [('district',0),('ballot_label',2),('party',3),('name',4)]}})
    if len({r['ballot_label'] for r in result}) != len(result): raise ValueError('duplicate candidate ballot label')
    return result, evidence(text, table)


def integer(text, *, signed=False):
    pattern = r'(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)'
    if not re.fullmatch(('-?' if signed else '') + pattern, text):
        raise ValueError('missing or invalid counting value')
    return int(text.replace(',', ''))


def counts(text, roster):
    table, rows = table_rows(text)
    header = [visible(c) for c in cells(rows[0])]
    if header != ['읍면동명', '구분', '선거인수', '투표수', '후보자별 득표수', '무효 투표수', '기권자수']:
        raise ValueError('counting table headers changed')
    candidate_header = [visible(c) for c in cells(rows[1])]
    if candidate_header != [r['party_at_election'] + ' ' + r['name'] for r in roster] + ['계']:
        raise ValueError('candidate roster and counting columns disagree')
    result = []
    for tr in rows[2:]:
        cs = cells(tr)
        if len(cs) != len(roster) + 7 or any(c['tag'] != 'td' for c in cs):
            raise ValueError('unsupported count row width/type')
        labels = [visible(c) for c in cs]; area, category = labels[:2]
        correction = area == '잘못 투입·구분된 투표지' and not category
        numbers = [integer(v, signed=correction and i == len(labels[2:])-1) for i, v in enumerate(labels[2:])]
        electors, ballots = numbers[:2]; votes = numbers[2:2+len(roster)]
        valid, invalid, abstentions = numbers[2+len(roster):]
        if sum(votes) != valid or valid + invalid != ballots or ballots + abstentions != electors:
            raise ValueError('counting row arithmetic mismatch')
        if area == '합계' and not category: kind = 'district_total'
        elif correction: kind = 'correction_leaf'
        elif area in {'거소투표', '관외사전투표'} and not category: kind = 'district_special_leaf'
        elif category == '계': kind = 'ward_subtotal'
        elif category in {'관내사전투표', '선거일투표'}: kind = 'ward_leaf'
        else: raise ValueError('unreviewed counting unit category')
        result.append({'area_displayed': area, 'category_displayed': category, 'row_kind': kind,
            'electors': electors, 'ballots': ballots, 'candidate_votes': votes, 'valid_votes': valid,
            'invalid_votes': invalid, 'abstentions': abstentions, 'source_row': evidence(text, tr),
            'physical_polling_place_id': None, 'physical_polling_place_link_verified': False})
    totals = [r for r in result if r['row_kind'] == 'district_total']
    if len(totals) != 1: raise ValueError('missing or duplicate district total')
    def vector(row): return [row[k] for k in ('electors','ballots')] + row['candidate_votes'] + [row[k] for k in ('valid_votes','invalid_votes','abstentions')]
    leaves = [r for r in result if r['row_kind'].endswith('_leaf')]
    if [sum(v) for v in zip(*(vector(r) for r in leaves))] != vector(totals[0]):
        raise ValueError('leaf units do not reconcile to district total')
    wards = {r['area_displayed'] for r in result if r['row_kind'] == 'ward_subtotal'}
    if any(r['row_kind'] == 'ward_leaf' and r['area_displayed'] not in wards for r in result):
        raise ValueError('ward leaf lacks subtotal')
    for ward in wards:
        subtotals = [r for r in result if r['row_kind'] == 'ward_subtotal' and r['area_displayed'] == ward]
        children = [r for r in result if r['row_kind'] == 'ward_leaf' and r['area_displayed'] == ward]
        if len(subtotals) != 1 or len({r['category_displayed'] for r in children}) != len(children):
            raise ValueError('duplicate ward totals/categories')
        if [sum(v) for v in zip(*(vector(r) for r in children))] != vector(subtotals[0]):
            raise ValueError('ward leaf arithmetic does not reconcile')
    return result, {'row_arithmetic': True, 'ward_partitions': True, 'district_leaf_partition': True,
                    'ward_count': len(wards), 'leaf_count': len(leaves)}, evidence(text, table)


def build(root=ROOT, *, write=True):
    root = Path(root); manifest_path = root / 'reports/nec-report-samples-latest.json'
    if not manifest_path.exists():
        report = {'schema': 'cheongju-nec-report-table-audit/1', 'status': 'NOT_COLLECTED', 'official_site_requests': 0}
    else:
        manifest = json.loads(manifest_path.read_bytes()); planned = {r['menu_id']: r for r in plans(root)}
        parsed, sources = {}, {}
        for source in manifest['sources']:
            menu = source['menu_id']
            if menu not in MENUS or menu in sources: raise ValueError('unexpected or duplicate report sample')
            expected = planned[menu]
            if (source['url'] != URL or source['method'] != 'POST'
                    or source['form_pairs'] != [list(p) for p in expected['form_pairs']]
                    or source['form_source_sha256'] != expected['form_source_sha256']):
                raise ValueError('report sample form provenance mismatch')
            path = (root / source['path']).resolve()
            if not path.is_relative_to((root / 'archive/elections/nec/report_responses').resolve()): raise ValueError('report sample path escape')
            raw = gzip.decompress(path.read_bytes())
            if sha(raw) != source['sha256'] or len(raw) != source['bytes']: raise ValueError('report sample hash/size mismatch')
            parsed[menu] = raw.decode('utf-8-sig')
            sources[menu] = {k: source[k] for k in ('url','method','form_pairs','path','sha256','bytes','captured_at')}
        if set(parsed) != set(MENUS): raise ValueError('report samples incomplete; no full sample audit')
        places, place_span = facilities(parsed['BIAP01'])
        roster, roster_span = candidates(parsed['CPRI03'])
        units, checks, unit_span = counts(parsed['VCCP08'], roster)
        report = {'schema': 'cheongju-nec-report-table-audit/1', 'status': 'VERIFIED_SAMPLE_TABLES_WITH_ARITHMETIC',
            'official_site_requests': 0, 'election_id': '0020260603', 'committee_scope': '청주시상당구',
            'district_scope': '청주시나선거구', 'polling_place_rows': len(places), 'candidate_rows': len(roster),
            'count_unit_rows': len(units), 'checks': checks, 'sources': sources,
            'table_spans': {'BIAP01': place_span, 'CPRI03': roster_span, 'VCCP08': unit_span},
            'facilities': places, 'candidates': roster, 'count_units': units,
            'whole_city_coverage_verified': False, 'seats_and_winners_verified': False,
            'ranks_calculated': 0, 'margins_calculated': 0, 'member_identity_promotions': 0,
            'physical_polling_place_vote_links_verified': False, 'html_connected': False}
    if write: write_json(root / 'reports/nec-report-table-audit-latest.json', report)
    return report


if __name__ == '__main__':
    r = build(); print(json.dumps({k: v for k, v in r.items() if k not in {'facilities','candidates','count_units','sources','table_spans'}}, ensure_ascii=False, indent=2))
