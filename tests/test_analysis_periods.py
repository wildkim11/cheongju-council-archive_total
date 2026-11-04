"""Synthetic interval fixtures; dates are not council facts."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from analysis_periods import (contains, day, days, exact_range, intersect, resolve,
                              tenure_window, union)
from audit_analysis_period_readiness import build

SCOPE = 'cheongju_integrated'
URL = 'https://council.cheongju.go.kr/example'


def evidence(start='2020-07-01', end='2024-06-30', term=2, half='whole'):
    return {'person_id': 'profile-A', 'council_scope': SCOPE, 'term': term,
            'half': half, 'start_date': start, 'end_date': end,
            'period_precision': 'exact_date', 'source_url': URL,
            'record_ref': 'synthetic:' + str(term) + ':' + half}


def selector(term=2, half='whole'):
    return {'council_scope': SCOPE, 'term': term, 'half': half}


class PeriodTests(unittest.TestCase):
    def test_strict_dates(self):
        for value in ['2024-02-30', '2024-2-01', '20240101', None, 2024, '2024-01-01T00:00:00Z']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                day(value)

    def test_single_day_inclusive_and_leap(self):
        self.assertEqual(days([('2024-02-29', '2024-02-29')]), 1)
        self.assertEqual(days([('2024-02-28', '2024-03-01')]), 3)
        self.assertTrue(contains([('2024-02-28', '2024-03-01')], '2024-03-01'))

    def test_overlap_duplicates_adjacency(self):
        self.assertEqual(union([('2024-01-02', '2024-01-03'), ('2024-01-01', '2024-01-02'),
                                ('2024-01-03', '2024-01-03')]), [('2024-01-01', '2024-01-03')])

    def test_gap_and_upper_bound(self):
        self.assertEqual(days([('9999-12-31', '9999-12-31')]), 1)
        self.assertEqual(len(union([('2020-01-01', '2020-01-01'), ('2020-01-03', '2020-01-03')])), 2)

    def test_reversed_empty_invalid_selection(self):
        for value in [{}, {'start_date': '2024-01-02', 'end_date': '2024-01-01'},
                      {'start_date': '2024-01-01'}, {'periods': {}}, {'typo': True}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve(value)

    def test_date_only_no_registry_needed(self):
        r = resolve({'start_date': '2024-06-30', 'end_date': '2024-07-01'})
        self.assertEqual(r['calendar_days'], 2)
        self.assertEqual(r['status'], 'RESOLVED')

    def test_july_boundary_not_calendar_year(self):
        r = resolve({'start_date': '2024-06-30', 'end_date': '2024-07-01', 'periods': [selector()]}, [evidence()])
        self.assertEqual(r['ranges'], [('2024-06-30', '2024-06-30')])

    def test_disjoint_terms_do_not_fill_skipped_term(self):
        records = [evidence('2016-07-01', '2020-06-30', 1), evidence('2024-07-01', '2028-06-30', 3)]
        r = resolve({'periods': [selector(1), selector(3), selector(1)]}, records)
        self.assertEqual(len(r['ranges']), 2)
        self.assertFalse(contains(r['ranges'], '2022-01-01'))
        self.assertEqual(len(r['evidence']), 2)

    def test_missing_half_holds_whole_selection(self):
        r = resolve({'periods': [selector(), selector(2, 'first')]}, [evidence()])
        self.assertEqual(r['status'], 'HELD')
        self.assertEqual(r['ranges'], [])

    def test_official_half_can_have_non_july_boundary(self):
        row = evidence('2020-07-03', '2022-07-07', half='first')
        r = resolve({'periods': [selector(half='first')]}, [row])
        self.assertEqual(r['ranges'], [('2020-07-03', '2022-07-07')])

    def test_duplicate_registry_is_held(self):
        self.assertEqual(resolve({'periods': [selector()]}, [evidence(), evidence()])['status'], 'HELD')

    def test_invalid_scope_bool_term_and_half(self):
        for k, v in [('council_scope', 'other'), ('term', True), ('half', 'winter')]:
            p = selector(); p[k] = v
            with self.assertRaises(ValueError):
                resolve({'periods': [p]})

    def test_exact_evidence_rejects_missing_conflict_and_bad_url(self):
        for patch in [{'end_date': None}, {'period_precision': 'start_exact_end_unknown'},
                      {'displayed_period_conflict': True}, {'source_url': 'https://example.org'},
                      {'source_url': 'https://user@council.cheongju.go.kr/'},
                      {'source_url': 'https://council.cheongju.go.kr:443/'}]:
            row = {**evidence(), **patch}
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                exact_range(row)

    def test_empty_intersection_is_explicit(self):
        r = resolve({'start_date': '2030-01-01', 'end_date': '2030-01-01', 'periods': [selector()]}, [evidence()])
        self.assertEqual(r['status'], 'EMPTY')
        self.assertEqual(r['calendar_days'], 0)

    def test_partial_tenure_election_resignation(self):
        r = resolve({'start_date': '2024-01-01', 'end_date': '2024-12-31'})
        t = tenure_window(r, [evidence('2024-04-05', '2024-08-31')], person_id='profile-A', council_scope=SCOPE, term=2)
        self.assertEqual(t['ranges'], [('2024-04-05', '2024-08-31')])
        self.assertEqual(t['denominator_days'], 149)

    def test_unknown_additional_tenure_blocks_denominator(self):
        r = resolve({'periods': [selector()]}, [evidence()])
        unknown = {**evidence(), 'end_date': None}
        t = tenure_window(r, [evidence(), unknown], person_id='profile-A', council_scope=SCOPE, term=2)
        self.assertEqual(t['status'], 'PARTIAL')
        self.assertIsNone(t['denominator_days'])

    def test_no_name_join_and_scope_term_isolation(self):
        r = resolve({'periods': [selector()]}, [evidence()])
        for patch in [{'person_id': 'profile-B', 'name': 'same'}, {'council_scope': 'cheongju_old_city'}, {'term': 1}]:
            t = tenure_window(r, [{**evidence(), **patch}], person_id='profile-A', council_scope=SCOPE, term=2)
            self.assertEqual(t['status'], 'HELD')
            self.assertIsNone(t['denominator_days'])

    def test_duplicate_tenure_does_not_double_days_and_input_immutable(self):
        r = resolve({'periods': [selector()]}, [evidence()]); original = copy.deepcopy(r)
        t = tenure_window(r, [evidence(), evidence()], person_id='profile-A', council_scope=SCOPE, term=2)
        self.assertEqual(t['recorded_days'], r['calendar_days'])
        self.assertEqual(r, original)

    def test_held_selection_and_no_matching_dates(self):
        t = tenure_window({'status': 'HELD'}, [], person_id='profile-A', council_scope=SCOPE, term=2)
        self.assertIsNone(t['denominator_days'])
        self.assertEqual(intersect([('2020-01-01', '2020-01-02')], [('2020-01-03', '2020-01-04')]), [])

    def test_repository_readiness_report_does_not_claim_completion(self):
        root = Path(__file__).resolve().parents[1]
        report = build(root, write=False)
        self.assertEqual(report['official_site_requests'], 0)
        self.assertFalse(report['seniority_filter_ready'])
        self.assertFalse(report['term_half_filter_ready'])
        self.assertEqual(report['datasets']['tenures']['rows'], report['analyzer_inputs']['tenures']['rows'])
        for value in report['datasets'].values():
            self.assertEqual(value['rows'], value['archived_explicit_interval_rows'] + value['held_rows'])


if __name__ == '__main__':
    unittest.main()
