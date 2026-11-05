"""Offline, partial election observations; never a complete district result.

Read only SHA-verified archived NEC name searches. Preserve displayed metrics,
literal detail-menu contracts and held identity evidence without executing JS,
guessing request parameters, inferring losses or calculating district ranks.
"""
import gzip
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from audit_nec_election_samples import DOM, build_current, find, visible, sha
from build_current_career_evidence import build as career_evidence
from link_nec_current_profiles import build as profile_links
from process_meeting_segments import encoded, write_json

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://info.nec.go.kr/'
ACTION = re.compile(r"fn_searchSelect\(this,'([^']+)','([^']*)','([A-Z0-9]+)'\);?")


def heading_fields(heading):
    """Strictly parse observed heading shape; missing metrics remain unknown."""
    parts = heading.split('/')
    if len(parts) not in (3, 4):
        raise ValueError('unexpected NEC heading separators')
    first = re.fullmatch(r'\[(\d{4}\.\d{2}\.\d{2})\]\s+(.+?)\s+([^\s/]+)', parts[0].strip())
    if not first:
        raise ValueError('unexpected NEC election title/party heading')
    location = re.fullmatch(r'충청북도\((청주시|청원군)([^()]*)\)\s*(당선)?', parts[2].strip())
    if not location:
        raise ValueError('unexpected NEC district heading')
    kind = parts[1].strip()
    if kind not in {'구·시·군의회의원선거', '기초의원비례대표선거'}:
        raise ValueError('unexpected municipal election kind')
    metrics = {'displayed_vote_count': None, 'displayed_vote_share_percent': None,
               'displayed_metrics_text': None, 'metrics_status': 'NOT_DISPLAYED',
               'vote_share_denominator': None, 'calculated_vote_share_percent': None}
    if len(parts) == 4:
        raw = parts[3].strip()
        m = re.fullmatch(r'(0|[1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*)표\s*\((\d{1,3}(?:\.\d+)?)%\)\s*(당선)?', raw)
        if not m or not 0 <= float(m[2]) <= 100 or location[3]:
            raise ValueError('invalid or conflicting NEC vote display')
        metrics.update(displayed_vote_count=int(m[1].replace(',', '')),
                       displayed_vote_share_percent=m[2], displayed_metrics_text=raw,
                       metrics_status='SOURCE_DISPLAY_ONLY_DENOMINATOR_UNVERIFIED')
    proportional = kind == '기초의원비례대표선거'
    return {'election_label': first[2], 'party_at_election': first[3],
            'election_kind_displayed': kind, 'district_displayed': location[1] + location[2],
            'representation': 'proportional' if proportional else 'district',
            'personal_vote_comparison_usable': False if proportional else metrics['displayed_vote_count'] is not None,
            'uncontested_status': 'UNVERIFIED', **metrics}


def source_menus(text, event):
    """Capture literal menu action and enclosing data; not executable transport."""
    observations = []
    for span in event['source_spans']:
        start, end = span['char_start'], span['char_end']
        raw = text[start:end]
        if sha(raw.encode()) != span['span_sha256']:
            raise ValueError('NEC event source span hash mismatch')
        dom = DOM(raw)
        lists = list(find(dom.root, lambda n: n['tag'] == 'div' and 'list' in n['attrs'].get('class', '').split()))
        if len(lists) != 1:
            raise ValueError('NEC event list shape changed')
        attributes = {k: v for k, v in lists[0]['attrs'].items() if k.startswith('data-')}
        for name, value in event['codes'].items():
            if attributes.get('data-' + name) != value:
                raise ValueError('NEC event coordinate mismatch')
        for node in find(lists[0], lambda n: n['tag'] == 'a' and 'onclick' in n['attrs']):
            action = node['attrs']['onclick']
            match = ACTION.fullmatch(action.strip())
            if not match:
                raise ValueError('unrecognized NEC detail-menu action')
            url = urljoin(BASE, match[1])
            u = urlsplit(url); query = parse_qs(u.query)
            if (u.scheme != 'https' or u.netloc != 'info.nec.go.kr' or u.path != '/main/showDocument.xhtml'
                    or u.fragment or len(query.get('secondMenuId', [])) != 1
                    or not re.fullmatch(r'[A-Z0-9]+', query['secondMenuId'][0])
                    or not re.fullmatch(r'\d{10}', query.get('electionId', [''])[0])):
                raise ValueError('unexpected NEC detail-menu URL')
            keys = match[2].split(',') if match[2] else []
            if any(not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9]*', k) for k in keys):
                raise ValueError('invalid NEC menu selector name')
            if node['end'] is None:
                raise ValueError('unclosed NEC menu source')
            a, b = start + node['start'], start + node['end']
            observations.append({'label': visible(node), 'menu_id': match[3], 'observed_url': url,
                'url_menu_id': query['secondMenuId'][0],
                'menu_id_discrepancy': query['secondMenuId'][0] != match[3],
                'selector_names': keys, 'enclosing_data_attributes': attributes,
                'onclick_literal': action, 'tab': span['tab'], 'char_start': a, 'char_end': b,
                'span_sha256': sha(text[a:b].encode()), 'transport_verified': False})
    return observations


def assemble(audit, links, careers, texts):
    linked = {}
    for row in links['rows']:
        if row['election_event_link_usable']:
            linked[(row['name'], row['linked_NEC_person_group'])] = row['current_profile_id']
    rows, held, targets = [], [], {}
    for event in audit['events']:
        if not event['target_local_council_scope']:
            continue
        try:
            fields = heading_fields(event['displayed_heading'])
            menus = source_menus(texts[event['source_response_path']], event)
        except ValueError as exc:
            held.append({'event_id': event['event_id'], 'reason': str(exc),
                         'source_response_sha256': event['source_response_sha256']})
            continue
        pid = linked.get((event['query_name'], event['nec_person_group_id']))
        row = {'event_id': event['event_id'], 'query_name': event['query_name'],
            'nec_person_group_id': event['nec_person_group_id'], 'election_date': event['election_date'],
            'current_profile_id': pid, 'identity_status': 'SOURCE_CORROBORATED_EVENT_LINK' if pid else 'HELD',
            'result_status': 'DISPLAYED_WINNER' if event['winner_tab_and_badge_confirmed'] else 'CANDIDACY_WITHOUT_CONFIRMED_RESULT',
            'source_url': event['source_url'], 'source_response_path': event['source_response_path'],
            'source_response_sha256': event['source_response_sha256'], 'source_spans': event['source_spans'],
            'displayed_heading': event['displayed_heading'], 'codes': event['codes'], **fields,
            'district_complete': False, 'candidate_count': None, 'seat_count': None,
            'rank': None, 'electoral_margin_votes': None, 'electoral_margin_percentage_points': None,
            'council_term': None, 'detail_menu_observations': menus}
        # Even a source-displayed personal vote does not resolve the person's identity.
        row['current_profile_comparison_usable'] = bool(pid and row['personal_vote_comparison_usable'])
        rows.append(row)
        for menu in menus:
            # Exact observed attributes retained: do not collapse districts based on labels.
            contract = {k: menu[k] for k in ('menu_id', 'observed_url', 'selector_names', 'enclosing_data_attributes')}
            key = sha(encoded(contract))
            target = targets.setdefault(key, {'target_id': 'nec-detail-target-' + key[:24], **contract,
                'transport_status': 'OBSERVED_MENU_ONLY_NOT_REQUEST_READY', 'source_event_ids': [], 'evidence': []})
            if event['event_id'] not in target['source_event_ids']:
                target['source_event_ids'].append(event['event_id'])
            target['evidence'].append({'event_id': event['event_id'], 'source_response_path': event['source_response_path'],
                'source_response_sha256': event['source_response_sha256'], **{k: menu[k] for k in
                    ('tab', 'char_start', 'char_end', 'span_sha256', 'onclick_literal', 'label')}})
    current = {p['profile_id']: p for p in careers['rows']}
    by_id = {e['event_id']: e for e in audit['events']}
    review = []
    for row in links['rows']:
        if row['election_event_link_usable']:
            continue
        p = current[row['current_profile_id']]
        review.append({'current_profile_id': row['current_profile_id'], 'name': row['name'],
            'hold_reasons': row['hold_reasons'], 'career_source_evidence': row['career_source_evidence'],
            'roster_response_evidence': row['roster_response_evidence'], 'current_careers': p['careers'],
            'anchors': [{'candidate_link': c, 'published_NEC_facts': by_id[c['anchor_event_id']]['published_profile_facts']}
                        for c in row['candidate_links']], 'decision': 'HELD_NO_PROMOTION'})
    return rows, held, sorted(targets.values(), key=lambda t: t['target_id']), review


def build(root=ROOT, *, write=True, periods_root=None):
    root = Path(root)
    audit = build_current(root, write=False)
    links = profile_links(root, write=False, periods_root=periods_root)
    careers = career_evidence(root, write=False)
    texts = {}
    for source in audit['sources']:
        if source['parse_status'] == 'VERIFIED_SOURCE':
            # build_current already verifies safe path, SHA, size and query provenance.
            texts[source['path']] = gzip.decompress((root / source['path']).read_bytes()).decode('utf-8-sig')
    rows, held, targets, review = assemble(audit, links, careers, texts)
    report = {'schema': 'cheongju-nec-election-observations/1', 'official_site_requests': 0,
        'status': 'PARTIAL_NAME_SEARCH_OBSERVATIONS_NOT_COMPLETE_DISTRICT_RESULTS',
        'input_audit_sha256': sha(encoded(audit)), 'input_profile_links_sha256': sha(encoded(links)),
        'source_target_events': sum(e['target_local_council_scope'] for e in audit['events']),
        'parsed_observations': len(rows), 'held_observations': len(held),
        'displayed_vote_observations': sum(r['displayed_vote_count'] is not None for r in rows),
        'missing_displayed_metrics': sum(r['metrics_status'] == 'NOT_DISPLAYED' for r in rows),
        'identity_linked_observations': sum(r['current_profile_id'] is not None for r in rows),
        'current_profile_vote_comparison_observations': sum(r['current_profile_comparison_usable'] for r in rows),
        'held_current_profiles': len(review), 'unique_observed_detail_contracts': len(targets),
        'detail_transport_verified': False, 'complete_districts': 0, 'ranks_calculated': 0,
        'margins_calculated': 0, 'exact_seniorities_confirmed': 0, 'html_connected': False,
        'rows': rows, 'held': held, 'detail_targets': targets, 'identity_review': review}
    if len(rows) + len(held) != report['source_target_events']:
        raise ValueError('NEC election observation conservation failure')
    if write:
        write_json(root / 'reports/nec-election-observations-latest.json', report)
    return report


if __name__ == '__main__':
    result = build()
    print(json.dumps({k: v for k, v in result.items() if k not in {'rows', 'held', 'detail_targets', 'identity_review'}}, ensure_ascii=False, indent=2))
