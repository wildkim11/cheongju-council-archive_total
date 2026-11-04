"""Synthetic profiles do not establish real-world identity or service dates."""
import copy
import json
import gzip
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_profile_history_evidence import build, derive, profile_code, preserved_rosters
from process_meeting_segments import sha

SCOPE = 'cheongju_integrated'
BASE = 'https://council.cheongju.go.kr'


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.photo = self.root / 'archive/people/portraits/sample.jpg'
        self.photo.parent.mkdir(parents=True)
        self.photo.write_bytes(b'synthetic portrait bytes')

    def fixture(self, term, pid=None, code='A12', name='시험인'):
        pid = pid or 'profile-' + str(term)
        p = {'person_id': pid, 'name': name, 'official_profile_code': code,
             'official_profile_code_type': 'mcode',
             'official_profile_url': f'{BASE}/include/memberProfile.html?daesu={term}&mcode={code}',
             'source_url': BASE + '/content/member/integrationCheongju.html',
             'portrait': {'local_path': 'archive/people/portraits/sample.jpg',
                          'sha256': sha(self.photo.read_bytes())}}
        t = {'person_id': pid, 'term': term, 'council_scope': SCOPE,
             'period_precision': 'term_only', 'start_date': None, 'end_date': None,
             'source_url': p['source_url']}
        return p, t

    def run_rows(self, pairs):
        return derive(self.root, [p for p, _ in pairs], [t for _, t in pairs])

    def test_scoped_code_and_identical_portrait_form_candidate_only(self):
        profiles, groups = self.run_rows([self.fixture(1), self.fixture(3)])
        self.assertEqual(groups[0]['status'], 'CORROBORATED_CANDIDATE')
        self.assertEqual(groups[0]['unobserved_terms_between'], [2])
        for row in profiles + groups:
            self.assertFalse(row['analysis_identity_usable'])
            self.assertIsNone(row['canonical_person_id'])
            self.assertIsNone(row['seniority'])

    def test_same_name_different_codes_never_link(self):
        _, groups = self.run_rows([self.fixture(1), self.fixture(3, code='B34')])
        self.assertEqual(groups, [])

    def test_code_reuse_with_different_name_held(self):
        _, groups = self.run_rows([self.fixture(1), self.fixture(2, name='다른인')])
        self.assertIn('official_code_name_conflict', groups[0]['hold_reasons'])

    def test_duplicate_profiles_in_same_term_held(self):
        _, groups = self.run_rows([self.fixture(1), self.fixture(1, pid='duplicate')])
        self.assertIn('same_term_multiple_profiles', groups[0]['hold_reasons'])

    def test_missing_portrait_held(self):
        pair = self.fixture(2); pair[0]['portrait'] = None
        _, groups = self.run_rows([self.fixture(1), pair])
        self.assertEqual(groups[0]['status'], 'HELD')

    def test_different_preserved_portraits_held(self):
        pair = self.fixture(2)
        other = self.photo.with_name('other.jpg'); other.write_bytes(b'other bytes')
        pair[0]['portrait'] = {'local_path': 'archive/people/portraits/other.jpg', 'sha256': sha(other.read_bytes())}
        _, groups = self.run_rows([self.fixture(1), pair])
        self.assertEqual(groups[0]['status'], 'HELD')

    def test_tampered_portrait_fails_before_writing(self):
        pair = self.fixture(1)
        self.photo.write_bytes(b'tampered')
        with self.assertRaises(ValueError): self.run_rows([pair])

    def test_portrait_path_escape_rejected(self):
        pair = self.fixture(1); pair[0]['portrait']['local_path'] = '../../elsewhere.jpg'
        with self.assertRaises(ValueError): self.run_rows([pair])

    def test_code_namespace_scope_term_and_url_validation(self):
        p, t = self.fixture(1)
        for patch in [{'official_profile_url': p['official_profile_url'].replace('daesu=1', 'daesu=2')},
                      {'official_profile_code_type': 'f_code'},
                      {'official_profile_url': p['official_profile_url'] + '&mcode=other'},
                      {'official_profile_url': p['official_profile_url'].replace('council.cheongju.go.kr', 'example.org')}]:
            with self.subTest(patch=patch): self.assertIsNone(profile_code({**p, **patch}, t))
        self.assertIsNone(profile_code(p, {**t, 'council_scope': 'cheongju_old_city'}))

    def test_fcode_not_joined_to_mcode(self):
        pair = self.fixture(4)
        pair[0].pop('official_profile_code_type')
        pair[0]['official_profile_url'] = BASE + '/memberHome/content/profile.html?f_code=A12'
        _, groups = self.run_rows([self.fixture(1), pair])
        self.assertEqual(groups, [])

    def test_personal_interval_not_council_period(self):
        p, t = self.fixture(1)
        t.update(start_date='2020-04-15', end_date='2021-02-28', period_precision='exact_date')
        ledger, _ = self.run_rows([(p, t)])
        self.assertEqual(ledger[0]['explicit_personal_intervals'][0]['start_date'], '2020-04-15')
        self.assertFalse(ledger[0]['complete_career_verified'])

    def test_conflicting_dates_stay_held(self):
        p, t = self.fixture(1)
        t.update(start_date='2020-04-15', end_date='2021-02-28', period_precision='exact_date', displayed_period_conflict=True)
        ledger, _ = self.run_rows([(p, t)])
        self.assertEqual(ledger[0]['explicit_personal_intervals'], [])
        self.assertEqual(len(ledger[0]['held_tenure_evidence']), 1)

    def test_missing_profiles_and_duplicate_ids_rejected(self):
        p, t = self.fixture(1)
        for people, tenures in [([], [t]), ([p, p], [t])]:
            with self.assertRaises(ValueError): derive(self.root, people, tenures)

    def test_invalid_tenure_does_not_bridge(self):
        p, t = self.fixture(1); other = {**t, 'term': 2}
        q, u = self.fixture(3)
        _, groups = derive(self.root, [p, q], [t, other, u])
        self.assertEqual(groups, [])

    def test_fragments_do_not_double_profile_or_change_inputs(self):
        p, t = self.fixture(1); q, u = self.fixture(3)
        source = copy.deepcopy([p, q, t, u])
        _, groups = derive(self.root, [p, q], [t, t, u])
        self.assertEqual(groups[0]['observed_terms'], [1, 3])
        self.assertEqual([p, q, t, u], source)

    def test_repository_evidence_references_and_determinism(self):
        root = Path(__file__).resolve().parents[1]
        report = build(root, write=False)
        self.assertEqual(report, build(root, write=False))
        self.assertEqual(report['profile_rows'], report['analyzer_inputs']['people']['rows'])
        self.assertEqual(report['canonical_identity_merges'], 0)
        self.assertEqual(report['seniority_decisions'], 0)
        self.assertEqual(report['official_term_half_registry_rows'], 0)
        self.assertEqual(report['official_site_requests'], 0)

    def test_preserved_roster_reparse_hashes_and_term_labels(self):
        html = '<li><a href="/include/memberProfile.html?daesu=1&mcode=A1">시험인 (1대:가 선거구)</a></li>'
        raw = html.encode('utf-8')
        directory = self.root / 'archive/source_responses'
        (directory / 'manifests').mkdir(parents=True)
        path = directory / 'example.html.gz'
        path.write_bytes(gzip.compress(raw))
        record = {'url': BASE + '/content/member/integrationCheongju.html',
                  'path': 'archive/source_responses/example.html.gz',
                  'bytes': len(raw), 'decoded_utf8_sha256': sha(raw)}
        manifest = directory / 'manifests/example.json'
        manifest.write_text(json.dumps({'schema': 'cheongju-source-responses/1', 'responses': [record]}))
        index, audit = preserved_rosters(self.root)
        self.assertEqual(audit['term_source_rows'], {'1': 1, '2': 0, '3': 0, '4': 0})
        self.assertEqual(len(index), 1)
        self.assertFalse(audit['official_periods_approved'])
        path.write_bytes(gzip.compress(raw + b'changed'))
        with self.assertRaises(ValueError): preserved_rosters(self.root)

    def test_preserved_response_path_escape_rejected(self):
        directory = self.root / 'archive/source_responses/manifests'
        directory.mkdir(parents=True)
        (directory / 'example.json').write_text(json.dumps({'schema': 'cheongju-source-responses/1',
            'responses': [{'url': BASE + '/content/member/integrationCheongju.html', 'path': '../../outside.gz'}]}))
        with self.assertRaises(ValueError): preserved_rosters(self.root)


if __name__ == '__main__': unittest.main()
