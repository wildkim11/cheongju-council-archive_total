import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_nec_report_tables as p


class ReportTableAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((p.ROOT / 'reports/nec-report-samples-latest.json').read_text())
        cls.texts = {s['menu_id']: gzip.decompress((p.ROOT / s['path']).read_bytes()).decode('utf-8-sig') for s in cls.manifest['sources']}
        cls.roster, _ = p.candidates(cls.texts['CPRI03'])

    def test_actual_facilities_retain_icons_and_source_ranges(self):
        rows, span = p.facilities(self.texts['BIAP01'])
        self.assertEqual(len(rows), 13)
        self.assertTrue(all(r['committee_displayed'] == '청주시상당구' for r in rows))
        self.assertIn('장애인화장실', rows[0]['accessibility_image_labels'])
        self.assertFalse(rows[0]['candidate_vote_link_verified'])
        self.assertIsNone(rows[0]['coordinates'])
        for r in rows:
            e = r['source_row']; self.assertEqual(p.sha(self.texts['BIAP01'][e['char_start']:e['char_end']].encode()), e['span_sha256'])

    def test_candidates_keep_ballot_label_separate_without_member_or_age_assignment(self):
        self.assertEqual(len(self.roster), 4)
        self.assertEqual(self.roster[0]['ballot_label'], '1-가')
        self.assertTrue(all(r['current_profile_id'] is None for r in self.roster))
        self.assertNotIn('1968.07.18', json.dumps(self.roster))

    def test_all_count_rows_reconcile_without_double_counting_subtotals(self):
        rows, checks, _ = p.counts(self.texts['VCCP08'], self.roster)
        self.assertEqual(len(rows), 19)
        self.assertTrue(checks['district_leaf_partition']); self.assertEqual(checks['leaf_count'], 13)
        grand = next(r for r in rows if r['row_kind'] == 'district_total')
        self.assertEqual(grand['ballots'], 32458); self.assertEqual(grand['valid_votes'], 30317)
        self.assertTrue(all(r['physical_polling_place_id'] is None for r in rows))

    def test_official_negative_correction_is_preserved_only_in_reviewed_field(self):
        rows, _, _ = p.counts(self.texts['VCCP08'], self.roster)
        r = next(r for r in rows if r['row_kind'] == 'correction_leaf')
        self.assertEqual(r['abstentions'], -49); self.assertEqual(r['electors'], 0)
        self.assertEqual(r['ballots'], 49)
        with self.assertRaises(ValueError): p.integer('-49')
        with self.assertRaises(ValueError): p.integer('')
        with self.assertRaises(ValueError): p.integer('-')

    def test_candidate_header_order_disagreement_is_held(self):
        with self.assertRaises(ValueError): p.counts(self.texts['VCCP08'], list(reversed(self.roster)))

    def test_changed_numeric_total_is_rejected(self):
        text = self.texts['VCCP08'].replace('9,251', '9,252', 1)
        with self.assertRaises(ValueError): p.counts(text, self.roster)

    def test_changed_or_unsupported_facility_shape_is_rejected(self):
        text = self.texts['BIAP01'].replace('임시기표소', '새로운필드', 1)
        # Caption text is not the header contract; change the actual header too.
        text = text.replace('임시기표소<br/>', '새로운필드<br/>')
        with self.assertRaises(ValueError): p.facilities(text)

    def test_missing_report_is_not_a_claim_of_zero_facilities(self):
        with tempfile.TemporaryDirectory() as td:
            r = p.build(td, write=False)
            self.assertEqual(r['status'], 'NOT_COLLECTED')
            self.assertNotIn('polling_place_rows', r)

    def test_tampered_report_source_retains_prior_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for folder in ('archive/elections/nec/detail_responses','archive/elections/nec/report_responses'):
                shutil.copytree(p.ROOT / folder, root / folder)
            (root / 'reports').mkdir()
            for name in ('nec-detail-source-probe-latest.json','nec-report-samples-latest.json'):
                shutil.copy2(p.ROOT / 'reports' / name, root / 'reports' / name)
            out = root / 'reports/nec-report-table-audit-latest.json'; out.write_bytes(b'prior-audit')
            source = self.manifest['sources'][0]
            (root / source['path']).write_bytes(gzip.compress(b'tampered'))
            with self.assertRaises(ValueError): p.build(root)
            self.assertEqual(out.read_bytes(), b'prior-audit')

    def test_actual_audit_does_not_promote_complete_city_winners_or_seats(self):
        r = p.build(write=False)
        self.assertEqual(r['polling_place_rows'], 13)
        self.assertEqual(r['candidate_rows'], 4)
        self.assertEqual(r['count_unit_rows'], 19)
        self.assertFalse(r['whole_city_coverage_verified'])
        self.assertFalse(r['seats_and_winners_verified'])
        self.assertFalse(r['physical_polling_place_vote_links_verified'])
        self.assertEqual(r['ranks_calculated'], 0)


if __name__ == '__main__': unittest.main()
