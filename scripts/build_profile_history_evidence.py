"""Offline review ledger for scoped profile links and explicit personal tenures.

No canonical identity merges, seniority decisions, or inferred council periods.
Repeated official codes are corroboration candidates, never identity approval.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
import gzip
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit

from analysis_periods import SCOPES, exact_range, official
from process_meeting_segments import encoded, load_export, sha, write_json
from collect_integrated_historical_members import parse_term_members, URL

ROOT = Path(__file__).resolve().parents[1]


def preserved_rosters(root):
    """Reparse hash-checked captured responses; never infer POST term from URL."""
    index, sources, manifests, seen = defaultdict(list), [], [], set()
    for path in sorted((root / 'archive/source_responses/manifests').glob('*.json')):
        raw_manifest = path.read_bytes()
        document = json.loads(raw_manifest)
        matching = [r for r in document.get('responses', []) if r.get('url') == URL]
        if not matching:
            continue
        if document.get('schema') != 'cheongju-source-responses/1':
            raise ValueError('invalid source response manifest')
        manifests.append({'path': str(path.relative_to(root)), 'sha256': sha(raw_manifest)})
        for record in matching:
            relative = record['path']
            source = (root / relative).resolve()
            if not source.is_relative_to((root / 'archive/source_responses').resolve()):
                raise ValueError('source response path escape')
            raw = gzip.decompress(source.read_bytes())
            if sha(raw) != record['decoded_utf8_sha256'] or len(raw) != record['bytes']:
                raise ValueError('roster source response hash or size mismatch')
            if relative in seen:
                continue
            seen.add(relative)
            html = raw.decode('utf-8')
            terms = []
            # POST selection hashes contain session tokens. Only the response's
            # explicit row labels/profile URLs establish which term was returned.
            for term in (1, 2, 3, 4):
                try:
                    rows = parse_term_members(html, term)
                except ValueError:
                    continue
                terms.append({'term': term, 'rows': len(rows)})
                for row in rows:
                    key = (term, row['official_profile_url'], row['name'])
                    index[key].append({'source_response_path': relative,
                        'decoded_utf8_sha256': sha(raw), 'source_manifest': str(path.relative_to(root)),
                        'parsed_row_sha256': sha(encoded(row)), 'parsed_row': row})
            sources.append({'path': relative, 'decoded_utf8_sha256': sha(raw), 'response_terms': terms})
    return index, {'response_count': len(sources), 'sources': sources, 'manifests': manifests,
                   'term_source_rows': {str(t): sum(1 for k in index if k[0] == t) for t in (1, 2, 3, 4)},
                   'official_periods_approved': False}


def ref(dataset, index, row):
    return {'row_ref': f'{dataset}:{index}', 'record_sha256': sha(encoded(row)),
            'source_url': row.get('source_url')}


def profile_code(person, tenure):
    """Validate namespace and term against the archived official profile URL."""
    url = person.get('official_profile_url')
    if not official(url):
        return None
    u = urlsplit(url)
    q = parse_qs(u.query, keep_blank_values=True)
    kind = person.get('official_profile_code_type')
    if kind is None and 'f_code' in q:
        kind = 'f_code'
    if kind not in {'mcode', 'f_code'}:
        return None
    if kind == 'mcode' and u.path != '/include/memberProfile.html':
        return None
    if kind == 'f_code' and u.path != '/memberHome/content/profile.html':
        return None
    # Scope mapping is deliberately limited to the integrated official portal.
    if tenure.get('council_scope') != 'cheongju_integrated':
        return None
    code = person.get('official_profile_code')
    if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9]+', code):
        return None
    if q.get(kind) != [code] or (kind == 'mcode' and q.get('daesu') != [str(tenure['term'])]):
        return None
    if kind == 'f_code' and tenure['term'] != 4:
        return None
    return kind, code


def portrait_evidence(root, person):
    p = person.get('portrait') or {}
    relative, expected = p.get('local_path'), p.get('sha256')
    if not isinstance(relative, str) or not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected):
        return None
    path = (root / relative).resolve()
    if not path.is_relative_to((root / 'archive/people/portraits').resolve()):
        raise ValueError('portrait path outside preserved portrait directory')
    if not path.is_file() or sha(path.read_bytes()) != expected:
        raise ValueError('portrait bytes missing or hash mismatch')
    return {'path': relative, 'sha256': expected}


def derive(root, people, tenures):
    profiles = {p['person_id']: (i, p) for i, p in enumerate(people, 1)}
    if len(profiles) != len(people):
        raise ValueError('duplicate profile ID')
    histories = defaultdict(list)
    for i, row in enumerate(tenures, 1):
        if row.get('person_id') not in profiles:
            raise ValueError('unknown tenure profile')
        if row.get('council_scope') not in SCOPES or type(row.get('term')) is not int or row['term'] < 1:
            raise ValueError('invalid tenure scope or term')
        histories[row['person_id']].append((i, row))
    ledger, buckets = [], defaultdict(list)
    for pid, (index, person) in profiles.items():
        history = histories[pid]
        intervals, held = [], []
        for i, row in history:
            evidence = {**ref('tenures', i, row), 'council_scope': row['council_scope'],
                        'term': row['term']}
            try:
                start, end = exact_range(row)
                intervals.append({**evidence, 'start_date': start, 'end_date': end})
            except ValueError as e:
                held.append({**evidence, 'reason': str(e)})
        if not history:
            held.append({'reason': 'no_tenure_rows'})
        portrait = portrait_evidence(root, person)
        item = {'profile_id': pid, 'name': person.get('name'),
                'profile_evidence': ref('people', index, person),
                'official_profile_url': person.get('official_profile_url'),
                'portrait_evidence': portrait, 'explicit_personal_intervals': intervals,
                'held_tenure_evidence': held, 'canonical_person_id': None,
                'seniority': None, 'complete_career_verified': False,
                'analysis_identity_usable': False}
        ledger.append(item)
        keys = set()
        for _, tenure in history:
            code = profile_code(person, tenure)
            if code:
                key = (tenure['council_scope'], *code)
                keys.add(key)
        # A profile with incompatible scopes/codes cannot bridge groups.
        if len(keys) == 1 and all(profile_code(person, tenure) for _, tenure in history):
            buckets[next(iter(keys))].append((item, history))
    groups = []
    for (scope, kind, code), members in sorted(buckets.items()):
        if len(members) < 2:
            continue
        reasons = []
        names = {m['name'] for m, _ in members}
        if len(names) != 1 or not all(names):
            reasons.append('official_code_name_conflict')
        portraits = {m['portrait_evidence']['sha256'] if m['portrait_evidence'] else None for m, _ in members}
        if None in portraits or len(portraits) != 1:
            reasons.append('portrait_corroboration_missing_or_different')
        terms = [r['term'] for _, h in members for _, r in h]
        # Multiple tenure fragments on one profile are allowed; two distinct
        # profiles claiming the same term require independent identity review.
        term_profiles = defaultdict(set)
        for m, h in members:
            for _, r in h:
                term_profiles[r['term']].add(m['profile_id'])
        if any(len(ids) > 1 for ids in term_profiles.values()):
            reasons.append('same_term_multiple_profiles')
        observed = sorted(set(terms))
        group = {'group_id': 'profile-link-' + sha(encoded([scope, kind, code]))[:20],
                 'council_scope': scope, 'official_code_type': kind, 'official_code': code,
                 'profile_ids': sorted(m['profile_id'] for m, _ in members),
                 'observed_terms': observed,
                 'unobserved_terms_between': [t for t in range(min(observed), max(observed) + 1) if t not in observed],
                 'status': 'HELD' if reasons else 'CORROBORATED_CANDIDATE',
                 'hold_reasons': reasons, 'analysis_identity_usable': False,
                 'canonical_person_id': None, 'seniority': None,
                 'complete_career_verified': False,
                 'interpretation': 'observed_terms_not_election_count_or_proof_of_absence'}
        groups.append(group)
    return ledger, groups


def build(root=ROOT, *, write=True, periods_root=None):
    root = Path(root).resolve()
    manifest = json.loads((root / 'exports/analyzer/manifest.json').read_text(encoding='utf-8'))
    data = {n: load_export(root, n, manifest) for n in ('people', 'tenures')}
    ledger, groups = derive(root, data['people'], data['tenures'])
    source_index, source_audit = preserved_rosters(root)
    backed_profiles = set()
    backed_intervals = 0
    for item in ledger:
        matches = []
        for tenure in item['explicit_personal_intervals'] + item['held_tenure_evidence']:
            if tenure.get('council_scope') != 'cheongju_integrated':
                continue
            candidates = source_index.get((tenure['term'], item['official_profile_url'], item['name']), [])
            exact = 'start_date' in tenure
            accepted = [r for r in candidates if not exact or (
                r['parsed_row']['start_date'] == tenure['start_date'] and
                r['parsed_row']['end_date'] == tenure['end_date'])]
            tenure['source_response_evidence'] = [{k: v for k, v in r.items() if k != 'parsed_row'} for r in accepted]
            if exact and accepted:
                backed_intervals += 1
            matches.extend(accepted)
        item['roster_response_backed'] = bool(matches)
        if matches:
            backed_profiles.add(item['profile_id'])
    for group in groups:
        group['all_profiles_roster_response_backed'] = all(p in backed_profiles for p in group['profile_ids'])
        if not group['all_profiles_roster_response_backed']:
            group['hold_reasons'].append('preserved_roster_response_missing')
            group['status'] = 'HELD'
    from verified_council_periods import load_verified
    period_basis = Path(periods_root).resolve() if periods_root is not None else root
    registry_path = period_basis / 'config/analysis_periods.json'
    if registry_path.exists():
        registry = json.loads(registry_path.read_text())
        boundary_path = period_basis / 'config/council_half_boundaries.json'
        boundaries = json.loads(boundary_path.read_text())['boundaries'] if boundary_path.exists() else None
        # Candidate source bytes/indexes are the validation root; configuration
        # may come from the operational root because candidate dirs omit config.
        period_rows = len(load_verified(root, registry, half_boundaries=boundaries))
    else:
        period_rows = None
    report = {'schema': 'cheongju-profile-history-evidence/1', 'official_site_requests': 0,
              'status': 'REVIEW_EVIDENCE_NOT_IDENTITY_APPROVAL',
              'analyzer_inputs': {n: manifest['datasets'][n] for n in data},
              'profile_rows': len(ledger), 'personal_interval_rows': sum(len(r['explicit_personal_intervals']) for r in ledger),
              'held_tenure_rows': sum(len(r['held_tenure_evidence']) for r in ledger),
              'candidate_groups': len(groups), 'group_statuses': dict(Counter(g['status'] for g in groups)),
              'candidate_profiles': len({p for g in groups for p in g['profile_ids']}),
              'canonical_identity_merges': 0, 'seniority_decisions': 0,
              'official_term_half_registry_rows': period_rows, 'analysis_identity_usable': False,
              'preserved_roster_audit': source_audit,
              'roster_response_backed_profiles': len(backed_profiles),
              'roster_response_backed_personal_intervals': backed_intervals,
              'next_evidence': ['official_roster_response_alignment_for_other_scopes_and_current_profiles',
                                'remaining_term4_half_and_legacy_council_dates_not_committee_dates',
                                'independent_cross_namespace_profile_identity_links',
                                'complete_scoped_election_history_including_preintegration']}
    outputs = {'profiles.jsonl': b''.join(encoded(r) for r in ledger),
               'link_candidates.jsonl': b''.join(encoded(g) for g in groups)}
    report['outputs'] = {n: {'path': 'exports/profile-history/' + n, 'sha256': sha(raw),
                             'bytes': len(raw), 'rows': len(raw.splitlines())} for n, raw in outputs.items()}
    if write:
        directory = root / 'exports/profile-history'
        directory.mkdir(parents=True, exist_ok=True)
        for name, raw in outputs.items():
            (directory / name).write_bytes(raw)
        write_json(directory / 'manifest.json', report)
        write_json(root / 'reports/profile-history-evidence-latest.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, default=ROOT)
    args = p.parse_args()
    print(json.dumps(build(args.root), ensure_ascii=False, indent=2))
