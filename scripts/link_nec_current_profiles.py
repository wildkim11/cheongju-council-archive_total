"""Narrow NEC-event links grounded in current name, district and independent career.

No canonical merges, exact seniority or complete-history claim. Observed wins
are a lower bound for the explicitly stated geographic history scope only.
"""
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata

from audit_nec_election_samples import build_current, build as sample_audit
from build_current_career_evidence import build as career_evidence
from build_career_roster_crosswalk import current_rosters
from process_meeting_segments import encoded, sha, write_json
from verified_council_periods import load_verified

ROOT = Path(__file__).resolve().parents[1]


def normalized_career(value):
    value = unicodedata.normalize('NFKC', value).strip()
    value = re.sub(r'^\s*(?:\((?:현|전)\)|(?:현|전)\))\s*', '', value)
    return re.sub(r'[^가-힣a-z0-9]', '', value.casefold())


def career_match(left, right):
    if any(word in left or word in right for word in ('청주시의회', '청원군의회')): return False
    a, b = normalized_career(left), normalized_career(right)
    if min(len(a), len(b)) < 8: return False
    return a == b or any(a == prefix+b or b == prefix+a for prefix in ('청주시', '충청북도', '충북'))


def district(value):
    value = re.sub(r'\s+', '', value)
    return re.sub(r'^청주시', '', value)


def district_matches(roster_district, event):
    if event.get('displayed_municipality') != '청주시': return False
    heading = event['displayed_heading']
    m = re.search(r'충청북도\s*\(([^)]+)\)', heading)
    if not m: return False
    if district(roster_district) == '비례대표':
        return '기초의원비례대표선거' in heading
    return district(roster_district) == district(m[1])


def reconcile(careers, roster, audit):
    results = []
    for profile in careers['rows']:
        pid, name = profile['profile_id'], profile['name']
        backing = roster.get((name, profile['source_url']), [])
        districts = {r['parsed_row']['district'] for r in backing if r['parsed_row'].get('district')}
        source_rows = [s for s in audit.get('sources', []) if s.get('query_name') == name and s.get('parse_status') == 'VERIFIED_SOURCE']
        row = {'current_profile_id': pid, 'name': name, 'status': 'HELD', 'election_event_link_usable': False,
               'canonical_identity_merge': False, 'complete_election_history_verified': False,
               'seniority_exact': None, 'observed_win_count_lower_bound': None,
               'at_least_two_observed_wins': None, 'candidate_links': [], 'hold_reasons': [],
               'geographic_two_win_filter_match': None,
               'count_scope': 'public_NEC_Cheongju_and_Cheongwon_municipal_council_history',
               'roster_response_evidence': backing, 'career_source_evidence': {k: profile[k] for k in
                    ('source_url', 'source_manifest', 'manifest_sha256', 'source_response_path', 'decoded_utf8_sha256', 'career_section_sha256')}}
        if len(source_rows) != 1:
            row['hold_reasons'].append('missing_or_duplicate_verified_NEC_name_query')
        if len(districts) != 1:
            row['hold_reasons'].append('missing_or_conflicting_source_backed_current_district')
        if row['hold_reasons']:
            results.append(row); continue
        for event in audit['events']:
            if (event['query_name'] != name or not event['target_local_council_scope']
                    or event['election_date'] != '2026-06-03'
                    or '제9회 전국동시지방선거' not in event['displayed_heading']
                    or not event['winner_tab_and_badge_confirmed']
                    or not district_matches(next(iter(districts)), event)):
                continue
            matches = []
            for career_index, text in enumerate(profile['careers'], 1):
                for fact in event.get('published_profile_facts', []):
                    if fact['tab'] != '당선인' or fact['field'] not in {'경력', '학력'}: continue
                    if career_match(text, fact['text']):
                        matches.append({'career_index': career_index, 'current_profile_quote': text,
                            'current_profile_quote_sha256': sha(text.encode()), 'NEC_profile_fact': fact,
                            'match_rule': 'full_normalized_phrase_or_explicit_local_jurisdiction_prefix'})
            row['candidate_links'].append({'nec_person_group_id': event['nec_person_group_id'],
                'anchor_event_id': event['event_id'], 'anchor_source_url': event['source_url'],
                'anchor_source_path': event['source_response_path'], 'anchor_source_sha256': event['source_response_sha256'],
                'anchor_source_spans': event['source_spans'], 'matched_district': next(iter(districts)),
                'independent_career_matches': matches, 'qualifies': bool(matches)})
        qualified = [c for c in row['candidate_links'] if c['qualifies']]
        if len(qualified) != 1:
            row['hold_reasons'].append('no_independent_career_match' if not qualified else 'multiple_qualified_NEC_groups')
            results.append(row); continue
        link = qualified[0]
        wins = [e for e in audit['events'] if e['nec_person_group_id'] == link['nec_person_group_id']
                and e['query_name'] == name and e['target_local_council_scope'] and e['winner_tab_and_badge_confirmed']]
        unique = {e['event_id']: e for e in wins}
        row.update(status='SOURCE_CORROBORATED_NEC_EVENT_LINK', election_event_link_usable=True,
            linked_NEC_person_group=link['nec_person_group_id'], observed_win_count_lower_bound=len(unique),
            at_least_two_observed_wins=len(unique) >= 2,
            geographic_two_win_filter_match=True if len(unique) >= 2 else None,
            observed_win_events=[{'event_id': e['event_id'], 'election_date': e['election_date'],
                                 'municipality': e['displayed_municipality'], 'source_url': e['source_url'],
                                 'source_response_sha256': e['source_response_sha256']} for e in sorted(unique.values(), key=lambda e: e['election_date'])])
        results.append(row)
    return results


def build(root=ROOT, *, write=True, periods_root=None):
    root = Path(root)
    if periods_root is None:
        periods = load_verified(root)
    else:
        definitions = Path(periods_root)
        registry = json.loads((definitions / 'config/analysis_periods.json').read_text())
        boundaries = json.loads((definitions / 'config/council_half_boundaries.json').read_text())['boundaries']
        periods = load_verified(root, registry, half_boundaries=boundaries)
    if not any(p['council_scope'] == 'cheongju_integrated' and p['term'] == 4 and p['half'] == 'whole' and p['start_date'] == '2026-07-01' for p in periods):
        raise ValueError('2026 current-profile scope lacks verified term-4 period')
    careers = career_evidence(root, write=False)
    roster = current_rosters(root, include_rows=True)
    audit = build_current(root, write=False)
    if audit['status'] == 'NOT_COLLECTED': audit = sample_audit(root, write=False)
    rows = reconcile(careers, roster, audit)
    report = {'schema': 'cheongju-NEC-current-profile-links/1', 'official_site_requests': 0,
        'status': 'PARTIAL_SOURCE_CORROBORATED_EVENT_LINKS_NOT_COMPLETE_SENIORITY',
        'career_input_sha256': sha(encoded(careers)), 'NEC_audit_sha256': sha(encoded(audit)),
        'current_profiles': len(rows), 'source_corroborated_event_links': sum(r['election_event_link_usable'] for r in rows),
        'held_profiles': sum(not r['election_event_link_usable'] for r in rows),
        'at_least_two_observed_win_profiles': sum(r['at_least_two_observed_wins'] is True for r in rows),
        'linked_observed_winning_events': sum(r['observed_win_count_lower_bound'] or 0 for r in rows),
        'geographic_two_win_filter_true': sum(r['geographic_two_win_filter_match'] is True for r in rows),
        'geographic_two_win_filter_unknown': sum(r['geographic_two_win_filter_match'] is None for r in rows),
        'hold_reasons': dict(Counter(reason for r in rows for reason in r['hold_reasons'])),
        'canonical_identity_merges': 0, 'exact_seniorities_confirmed': 0, 'html_filters_connected': False, 'rows': rows,
        'interpretation': 'Current name + source-backed current district + explicit 2026 NEC winner + independent full career/education phrase. Scope limited to NEC events linked to current profile. Observed wins are geographic lower bounds; exact seniority, complete history, historical council profile merges and HTML filters remain unconfirmed.'}
    if write: write_json(root / 'reports/nec-current-profile-links-latest.json', report)
    return report


if __name__ == '__main__':
    r = build(); print(json.dumps({k: v for k, v in r.items() if k != 'rows'}, ensure_ascii=False, indent=2))
