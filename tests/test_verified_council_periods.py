import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verified_council_periods import derive, load_verified, node_period, sha, TREE_URL
from analysis_periods import resolve


class VerifiedPeriodTests(unittest.TestCase):
    def node(self):
        return {'text': '제2대 의회(2018. 07. 01 ~ 2022. 06. 30 : 제035회 ~ 제070회)',
                'var01': '2', 'var11': 'SvcMntsTreeGnrtnSesn'}

    def fixture(self, root, nodes=None):
        raw = json.dumps(nodes or [self.node()], ensure_ascii=False).encode()
        relative = 'archive/source_responses/' + sha(raw) + '.html.gz'
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(raw, mtime=0))
        doc = {'schema': 'cheongju-source-responses/1', 'responses': [
            {'url': TREE_URL, 'path': relative, 'decoded_utf8_sha256': sha(raw), 'bytes': len(raw)}]}
        encoded = json.dumps(doc).encode()
        manifest = root / 'archive/source_responses/manifests' / (sha(encoded) + '.json')
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(encoded)
        return path, manifest

    def test_explicit_label_not_opening_day_formula(self):
        row = node_period(self.node())
        self.assertEqual((row['start_date'], row['end_date']), ('2018-07-01', '2022-06-30'))
        self.assertEqual(row['half'], 'whole')
        self.assertIn('not_elapsed_service', row['period_kind'])

    def test_term_code_and_dates_must_match(self):
        for patch in [{'var01': '3'}, {'var11': 'other'},
                      {'text': self.node()['text'].replace('07. 01', '02. 30')}]:
            with self.assertRaises(ValueError): node_period({**self.node(), **patch})

    def test_fullterm_registry_verifies_from_bytes_and_half_stays_held(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            rows = derive(root)
            registry = {'schema': 'cheongju-analysis-period-registry/1', 'periods': rows}
            self.assertEqual(load_verified(root, registry), rows)
            selection = {'periods': [{'council_scope': 'cheongju_integrated', 'term': 2, 'half': 'whole'}]}
            self.assertEqual(resolve(selection, rows)['status'], 'RESOLVED')
            selection['periods'][0]['half'] = 'first'
            self.assertEqual(resolve(selection, rows)['status'], 'HELD')

    def test_changed_registered_date_scope_or_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            rows = derive(root)
            for patch in [{'start_date': '2018-07-03'}, {'council_scope': 'cheongju_old_city'},
                          {'source_evidence': []}, {'half': 'first'}]:
                changed = [{**rows[0], **patch}]
                with self.assertRaises(ValueError):
                    load_verified(root, {'schema': 'cheongju-analysis-period-registry/1', 'periods': changed})

    def test_response_or_manifest_tamper_rejected(self):
        for which in ('response', 'manifest'):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp); path, manifest = self.fixture(root)
                if which == 'response': path.write_bytes(gzip.compress(b'[]'))
                else: manifest.write_bytes(manifest.read_bytes() + b' ')
                with self.assertRaises(ValueError): derive(root)

    def test_conflicting_root_dates_and_duplicate_terms_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            other = self.node(); other['text'] = other['text'].replace('2018. 07. 01', '2018. 07. 03')
            self.fixture(root, [other])
            with self.assertRaises(ValueError): derive(root)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root, [self.node(), self.node()])
            with self.assertRaises(ValueError): derive(root)

    def test_registry_duplicate_or_unbacked_term_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            rows = derive(root)
            for records in (rows + rows, [{**rows[0], 'record_ref': 'invented'}]):
                with self.assertRaises(ValueError):
                    load_verified(root, {'schema': 'cheongju-analysis-period-registry/1', 'periods': records})

    def test_new_corroborating_capture_preserves_registered_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            registry = {'schema': 'cheongju-analysis-period-registry/1', 'periods': derive(root)}
            self.fixture(root, [{**self.node(), 'id': 'new-session-root-id'}])
            self.assertEqual(len(derive(root)[0]['source_evidence']), 2)
            self.assertEqual(load_verified(root, registry), registry['periods'])

    def test_real_registry_four_whole_terms_only(self):
        root = Path(__file__).resolve().parents[1]
        rows = load_verified(root)
        self.assertEqual([r['term'] for r in rows], [1, 2, 3, 4])
        self.assertTrue(all(r['half'] == 'whole' and len(r['source_evidence']) >= 1 for r in rows))
