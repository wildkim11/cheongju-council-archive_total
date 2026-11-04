"""Hash-checked archived interval readiness; no HTTP and no identity inference."""
from pathlib import Path
import argparse
import collections
import json
from analysis_periods import exact_range
from process_meeting_segments import load_export, write_json
from verified_council_periods import load_verified

ROOT = Path(__file__).resolve().parents[1]


def build(root=ROOT, *, write=True):
    root = Path(root)
    manifest = json.loads((root / 'exports/analyzer/manifest.json').read_text())
    result = {}
    names = ('tenures', 'party_memberships', 'committee_memberships', 'district_memberships')
    for name in names:
        rows = load_export(root, name, manifest)
        reasons = collections.Counter()
        exact = 0
        for row in rows:
            try:
                exact_range(row)
                exact += 1
            except ValueError as e:
                reasons[str(e)] += 1
        result[name] = {'rows': len(rows),
                        'start_date_present': sum(bool(r.get('start_date')) for r in rows),
                        'end_date_present': sum(bool(r.get('end_date')) for r in rows),
                        'archived_explicit_interval_rows': exact,
                        'held_rows': len(rows) - exact, 'hold_reasons': dict(reasons)}
    registry = json.loads((root / 'config/analysis_periods.json').read_text())
    periods = load_verified(root, registry)
    report = {'schema': 'cheongju-analysis-period-readiness/1',
              'status': 'INCOMPLETE_EVIDENCE', 'official_site_requests': 0,
              'analyzer_inputs': {n: manifest['datasets'][n] for n in names},
              'datasets': result, 'official_period_registry_rows': len(periods),
              'verified_whole_term_selectors': [
                  {k: row[k] for k in ('council_scope', 'term', 'half')} for row in periods],
              'whole_term_periods_source_verified': bool(periods),
              'half_term_periods_source_verified': False,
              'seniority_filter_ready': False, 'term_half_filter_ready': False,
              'missing_contracts': ['verified_cross_profile_person_links',
                  'complete_scoped_election_or_service_history',
                  'dated_official_half_and_legacy_scope_boundaries'],
              'interpretation': 'field_and_archived_interval_readiness_not_human_verified_history',
              'html_filters_connected': False}
    if write:
        write_json(root / 'reports/analysis-period-readiness-latest.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(build(args.root), ensure_ascii=False, indent=2))
