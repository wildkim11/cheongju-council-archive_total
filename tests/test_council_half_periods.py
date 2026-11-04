import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from council_half_periods import derive_halves
from analysis_periods import resolve, union, days
from verified_council_periods import load_verified

ROOT = Path(__file__).resolve().parents[1]


class HalfPeriodTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.boundaries = json.loads((ROOT / 'config/council_half_boundaries.json').read_text())['boundaries']
        self.whole = [r for r in json.loads((ROOT / 'config/analysis_periods.json').read_text())['periods'] if r['half'] == 'whole']
        meetings = json.loads((ROOT / 'indexes/integrated/meetings.json').read_text())
        ids = {b['source']['meeting_id'] for b in self.boundaries}
        self.meetings = [m for m in meetings if m['meeting_id'] in ids]
        p = self.root / 'indexes/integrated/meetings.json'
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(self.meetings))
        for row in self.boundaries:
            target = self.root / row['source']['source_path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row['source']['source_path'], target)

    def run_rows(self, rows=None):
        return derive_halves(self.root, self.whole, self.boundaries if rows is None else rows)

    def test_three_boundaries_partition_whole_without_gaps_or_overlap(self):
        halves = self.run_rows()
        self.assertEqual(len(halves), 6)
        for whole in self.whole[:3]:
            rows = [r for r in halves if r['term'] == whole['term']]
            ranges = [(r['start_date'], r['end_date']) for r in rows]
            self.assertEqual(union(ranges), [(whole['start_date'], whole['end_date'])])
            self.assertEqual(sum(days([r]) for r in ranges), days(union(ranges)))

    def test_calendar_july1_not_july4_chair_election(self):
        half = next(r for r in self.run_rows() if r['term'] == 1 and r['half'] == 'second')
        self.assertEqual(half['start_date'], '2016-07-01')
        self.assertIn('personal_office_contrast', str(half['source_evidence']))
        self.assertIn('not_personal_office', half['period_kind'])

    def test_term4_halves_not_synthesized(self):
        self.assertFalse(any(r['term'] == 4 for r in self.run_rows()))
        selection = {'periods': [{'council_scope': 'cheongju_integrated', 'term': 4, 'half': 'first'}]}
        self.assertEqual(resolve(selection, self.whole + self.run_rows())['status'], 'HELD')

    def test_modified_calendar_date_rejected_for_each_interpretation_rule(self):
        for i, bad in enumerate(['2016-07-04', '2020-07-02', '2024-07-02']):
            rows = copy.deepcopy(self.boundaries)
            rows[i]['boundary_date'] = bad
            with self.subTest(term=i+1), self.assertRaises(ValueError): self.run_rows(rows)

    def test_source_bytes_tamper_rejected(self):
        p = self.root / self.boundaries[0]['source']['source_path']
        p.write_bytes(p.read_bytes() + b'tampered')
        with self.assertRaises(ValueError): self.run_rows()

    def test_quote_coordinates_hash_and_speaker_all_checked(self):
        for field, value in [('char_start', 0), ('quote_sha256', '0' * 64),
                             ('quote', 'different'), ('speaker_name', '다른사람'), ('speaker_role', '의장')]:
            rows = copy.deepcopy(self.boundaries)
            rows[0]['excerpts'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.run_rows(rows)

    def test_scope_duplicate_missing_parent_and_unreviewed_rule_rejected(self):
        for field, value in [('council_scope', 'cheongju_old_city'), ('calendar_kind', 'chair_tenure'),
                             ('interpretation_rule', 'two_year_formula'), ('term', 8)]:
            rows = copy.deepcopy(self.boundaries); rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.run_rows(rows)
        with self.assertRaises(ValueError): self.run_rows(self.boundaries + [self.boundaries[0]])

    def test_wrong_source_url_or_meeting_metadata_rejected(self):
        rows = copy.deepcopy(self.boundaries); rows[0]['source']['source_url'] = 'https://example.org/'
        with self.assertRaises(ValueError): self.run_rows(rows)
        self.meetings[0]['date'] = '2000-01-01'
        (self.root / 'indexes/integrated/meetings.json').write_text(json.dumps(self.meetings))
        with self.assertRaises(ValueError): self.run_rows()

    def test_mixed_selection_holds_if_any_half_unverified(self):
        rows = load_verified(ROOT)
        selected = {'periods': [{'council_scope': 'cheongju_integrated', 'term': 1, 'half': 'first'},
                                {'council_scope': 'cheongju_integrated', 'term': 4, 'half': 'second'}]}
        self.assertEqual(resolve(selected, rows)['status'], 'HELD')

    def test_direct_dates_intersect_noncontinuous_halves(self):
        rows = load_verified(ROOT)
        selected = {'periods': [{'council_scope': 'cheongju_integrated', 'term': 1, 'half': 'first'},
                                {'council_scope': 'cheongju_integrated', 'term': 3, 'half': 'second'}],
                    'start_date': '2016-06-30', 'end_date': '2024-07-01'}
        result = resolve(selected, rows)
        self.assertEqual(result['ranges'], [('2016-06-30', '2016-06-30'), ('2024-07-01', '2024-07-01')])

    def test_registered_half_date_or_provenance_tamper_rejected(self):
        registry = json.loads((ROOT / 'config/analysis_periods.json').read_text())
        for patch in [{'start_date': '2016-07-04'}, {'source_evidence': []}]:
            changed = copy.deepcopy(registry)
            row = next(r for r in changed['periods'] if r['term'] == 1 and r['half'] == 'second')
            row.update(patch)
            with self.assertRaises(ValueError): load_verified(ROOT, changed)
