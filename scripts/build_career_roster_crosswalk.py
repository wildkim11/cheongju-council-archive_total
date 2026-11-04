"""Cross-check explicit profile career mentions against archived council rosters.

Corroborated review candidates are not person merges, elections or seniorities.
No negative inference from missing terms or incomplete career summaries.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import re

from build_current_career_evidence import build as career_evidence
from build_profile_history_evidence import preserved_rosters
from collect_current_members import LIST_URL, parse_member_index
from process_meeting_segments import encoded, load_export, sha, write_json

ROOT = Path(__file__).resolve().parents[1]
TERM_LIST = re.compile(r'(?P<integrated>통합\s*)?제\s*(?P<values>\d+(?:\s*대?\s*[,·ㆍ]\s*(?:제\s*)?\d+)*)\s*대\s*(?P<council>청주시의회|청원군의회)')


def parse_claim(text):
    """Expand explicit enumerations only; do not expand ranges or office cohorts."""
    matches = list(TERM_LIST.finditer(text))
    if len(matches) != 1:
        return {'status': 'HELD', 'reason': 'missing_or_multiple_council_term_expressions', 'terms': []}
    m = matches[0]
    terms = [int(n) for n in re.findall(r'\d+', m['values'])]
    if not terms or any(n < 1 for n in terms) or len(terms) != len(set(terms)):
        return {'status': 'HELD', 'reason': 'invalid_or_duplicate_term_numbers', 'terms': []}
    label = 'current' if re.match(r'^현\s*\)', text) else 'former' if re.match(r'^전\s*\)', text) else 'unspecified'
    if label == 'unspecified':
        return {'status': 'HELD', 'reason': 'missing_current_or_former_label', 'terms': []}
    return {'status': 'EXPLICIT_TERM_MENTION', 'terms': terms, 'career_label': label,
        'council_label': m['council'], 'scope_explicitly_integrated': bool(m['integrated']),
        'expression': m[0], 'expression_char_start': m.start(), 'expression_char_end': m.end(),
        'office_text': text[m.end():].strip(), 'scope_verified': False}


def current_rosters(root):
    index = defaultdict(list)
    seen = set()
    for manifest in sorted((root / 'archive/source_responses/manifests').glob('*.json')):
        raw_manifest = manifest.read_bytes()
        document = json.loads(raw_manifest)
        for response in document.get('responses', []):
            if response.get('url') != LIST_URL:
                continue
            if document.get('schema') != 'cheongju-source-responses/1' or manifest.stem != sha(raw_manifest):
                raise ValueError('current roster manifest hash or schema mismatch')
            path = (root / response['path']).resolve()
            if not path.is_relative_to((root / 'archive/source_responses').resolve()):
                raise ValueError('current roster source path escape')
            raw = gzip.decompress(path.read_bytes())
            if sha(raw) != response['decoded_utf8_sha256'] or len(raw) != response['bytes']:
                raise ValueError('current roster response hash or size mismatch')
            if response['path'] in seen:
                continue
            seen.add(response['path'])
            for row in parse_member_index(raw.decode('utf-8')):
                index[(row['name'], row['profile_url'])].append({
                    'source_manifest': str(manifest.relative_to(root)),
                    'manifest_sha256': sha(raw_manifest), 'source_response_path': response['path'],
                    'decoded_utf8_sha256': sha(raw), 'parsed_row_sha256': sha(encoded(row))})
    return index


def crosswalk(careers, people, tenures, historical, current):
    people_index = {p['person_id']: (i, p) for i, p in enumerate(people, 1)}
    if len(people_index) != len(people):
        raise ValueError('duplicate profile ID in career crosswalk')
    by_name_term = defaultdict(dict)
    for i, t in enumerate(tenures, 1):
        if t['person_id'] not in people_index:
            raise ValueError('career crosswalk tenure references missing profile')
        _, person = people_index[t['person_id']]
        key = person['name'], t['term']
        candidate_key = t['council_scope'], person['person_id']
        if candidate_key not in by_name_term[key]:
            by_name_term[key][candidate_key] = {'profile_id': person['person_id'],
                'council_scope': t['council_scope'], 'term': t['term'],
                'official_profile_url': person.get('official_profile_url'),
                'profile_row_ref': 'people:' + str(people_index[t['person_id']][0]),
                'profile_record_sha256': sha(encoded(person)), 'tenure_evidence': []}
        by_name_term[key][candidate_key]['tenure_evidence'].append({
            'row_ref': 'tenures:' + str(i), 'record_sha256': sha(encoded(t))})
    mentions, groups, profiles = [], {}, {}
    for source in careers['rows']:
        pid = source['profile_id']
        if pid not in people_index or people_index[pid][1]['name'] != source['name']:
            raise ValueError('career crosswalk current profile/name mismatch')
        summary = profiles.setdefault(pid, {'profile_id': pid, 'name': source['name'],
            'explicit_term_mentions': [], 'source_backed_candidate_terms': [],
            'unobserved_terms_between_mentions': [], 'current_roster_period_evidence': [], 'seniority': None,
            'complete_career_verified': False, 'analysis_identity_usable': False})
        current_person = people_index[pid][1]
        current_backing = current.get((source['name'], current_person.get('official_profile_url')), [])
        if current_backing:
            summary['current_roster_period_evidence'] = [{'council_scope': 'cheongju_integrated',
                'term': 4, 'profile_id': pid, 'roster_response_evidence': current_backing}]
            summary['source_backed_candidate_terms'].append(4)
        for career_index, text in enumerate(source['careers'], 1):
            if text not in source['numbered_council_career_mentions']:
                continue
            parsed = parse_claim(text)
            mention = {'current_profile_id': pid, 'name': source['name'], 'career_index': career_index,
                'quote': text, 'quote_sha256': sha(text.encode()), 'parsed': parsed,
                'career_source': {k: source[k] for k in ('source_url', 'source_manifest', 'manifest_sha256',
                    'source_response_path', 'decoded_utf8_sha256', 'career_section_sha256')},
                'candidates_by_term': [], 'seniority_usable': False, 'election_fact': False}
            for term in parsed['terms']:
                expected_scopes = {'cheongwon_old_county'} if parsed['council_label'] == '청원군의회' else {'cheongju_integrated'} if parsed['scope_explicitly_integrated'] else {'cheongju_integrated', 'cheongju_old_city'}
                candidates = []
                for (scope, candidate_pid), candidate in by_name_term[(source['name'], term)].items():
                    if scope not in expected_scopes:
                        continue
                    if scope == 'cheongju_integrated' and term in (1, 2, 3):
                        backing = [{k: v for k, v in r.items() if k != 'parsed_row'} for r in historical.get((term, candidate['official_profile_url'], source['name']), [])]
                    elif scope == 'cheongju_integrated' and term == 4 and candidate_pid == pid:
                        backing = current.get((source['name'], candidate['official_profile_url']), [])
                    else:
                        backing = []
                    item = {**candidate, 'roster_response_evidence': backing,
                        'status': 'SOURCE_BACKED_REVIEW_CANDIDATE' if backing else 'HELD_NO_REPARSED_ROSTER_RESPONSE',
                        'analysis_identity_usable': False, 'canonical_person_id': None}
                    candidates.append(item)
                    key = pid, scope, term, candidate_pid
                    group = groups.setdefault(key, {**item, 'current_profile_id': pid,
                        'name': source['name'], 'career_mentions': [], 'seniority': None})
                    group['career_mentions'].append({'career_index': career_index,
                        'quote_sha256': mention['quote_sha256'], 'career_source_sha256': source['decoded_utf8_sha256']})
                    if backing:
                        summary['source_backed_candidate_terms'].append(term)
                mention['candidates_by_term'].append({'term': term, 'candidates': candidates,
                    'status': 'NO_ROSTER_CANDIDATE' if not candidates else 'AMBIGUOUS_MULTIPLE_ROSTER_CANDIDATES' if len(candidates) > 1 else 'REVIEW_CANDIDATES',
                    'absence_is_election_loss': False})
                summary['explicit_term_mentions'].append(term)
            mentions.append(mention)
    for summary in profiles.values():
        for field in ('explicit_term_mentions', 'source_backed_candidate_terms'):
            summary[field] = sorted(set(summary[field]))
        terms = summary['source_backed_candidate_terms']
        if terms:
            summary['unobserved_terms_between_mentions'] = [t for t in range(min(terms), max(terms)+1) if t not in terms]
        summary['unobserved_terms_are_losses'] = False
        summary['gap_scope'] = 'cheongju_integrated_review_candidates_only'
    return mentions, list(groups.values()), list(profiles.values())


def build(root=ROOT, *, write=True):
    root = Path(root)
    manifest = json.loads((root / 'exports/analyzer/manifest.json').read_text())
    people = load_export(root, 'people', manifest)
    tenures = load_export(root, 'tenures', manifest)
    careers = career_evidence(root, write=False)
    historical, source_audit = preserved_rosters(root)
    current = current_rosters(root)
    mentions, candidates, profiles = crosswalk(careers, people, tenures, historical, current)
    report = {'schema': 'cheongju-career-roster-crosswalk/1', 'status': 'REVIEW_CANDIDATES_NOT_ELECTION_HISTORY',
        'official_site_requests': 0, 'analyzer_inputs': {k: manifest['datasets'][k] for k in ('people', 'tenures')},
        'career_evidence_sha256': sha(encoded(careers)), 'career_mentions': len(mentions),
        'expanded_term_mentions': sum(len(m['parsed']['terms']) for m in mentions),
        'held_mentions': sum(m['parsed']['status'] == 'HELD' for m in mentions),
        'profile_term_candidates': len(candidates),
        'source_backed_profile_term_candidates': sum(bool(c['roster_response_evidence']) for c in candidates),
        'candidate_statuses': dict(Counter(c['status'] for c in candidates)),
        'current_roster_backed_profiles': len(current), 'historical_roster_response_count': source_audit['response_count'],
        'profiles_with_noncontinuous_mentions': sum(bool(p['unobserved_terms_between_mentions']) for p in profiles),
        'official_election_facts': 0, 'canonical_identity_merges': 0, 'seniority_decisions': 0,
        'mentions': mentions, 'candidates': candidates, 'profiles': profiles,
        'interpretation': 'Explicit self-profile term mentions cross-checked with scoped names and source-backed rosters. Review candidates only; missing terms are not losses; career summaries are incomplete; no election count or seniority.'}
    if write:
        write_json(root / 'reports/career-roster-crosswalk-latest.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT)
    args = p.parse_args(); result = build(args.root)
    print(json.dumps({k: v for k, v in result.items() if k not in ('mentions', 'candidates', 'profiles')}, ensure_ascii=False, indent=2))
