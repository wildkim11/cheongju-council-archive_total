import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_council_period_sources import audit, excerpts, sha, URLS


class PeriodAuditTests(unittest.TestCase):
    def fixture(self, root, url=None, relative=None, digest=None):
        raw = '<html><p>제1대 전반기 2014. 7. 1.</p></html>'.encode()
        relative = relative or 'archive/source_responses/' + sha(raw) + '.html.gz'
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(raw, mtime=0))
        row = {'url': url or sorted(URLS)[0], 'path': relative,
               'decoded_utf8_sha256': digest or sha(raw), 'bytes': len(raw)}
        document = {'schema': 'cheongju-source-responses/1', 'responses': [row]}
        encoded = json.dumps(document).encode()
        manifest = root / 'archive/source_responses/manifests' / (sha(encoded) + '.json')
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_bytes(encoded)
        return path, manifest

    def test_missing_sources_are_explicit(self):
        with tempfile.TemporaryDirectory() as root:
            result = audit(root)
            self.assertEqual(result['status'], 'MISSING_SOURCES')
            self.assertEqual(len(result['missing_source_urls']), 3)

    def test_unicode_positions_and_context_do_not_promote(self):
        rows = excerpts('<p>안내</p>\n<p>제1대 전반기</p>\n<p>2014. 7. 1.</p>')
        self.assertEqual(rows[0]['html_line'], 2)
        self.assertEqual(rows[0]['html_column'], 3)
        self.assertEqual(rows[0]['context'][0]['text'], '안내')
        self.assertTrue(all(not r['period_usable'] for r in rows))

    def test_script_style_and_comments_excluded(self):
        self.assertEqual(excerpts('<script>제1대</script><style>전반기</style><!--후반기-->'), [])

    def test_preserved_response_and_manifest_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = audit(root)
            self.assertEqual(result['source_versions'], 1)
            self.assertEqual(result['official_periods_promoted'], 0)
            self.assertEqual(result['official_site_requests'], 0)

    def test_tampered_response_fails_before_report_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, _ = self.fixture(root)
            audit(root)
            output = root / 'reports/council-period-source-evidence-latest.json'
            before = output.read_bytes()
            path.write_bytes(gzip.compress(b'tampered'))
            with self.assertRaises(ValueError): audit(root)
            self.assertEqual(output.read_bytes(), before)

    def test_tampered_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, manifest = self.fixture(root)
            manifest.write_bytes(manifest.read_bytes() + b' ')
            with self.assertRaises(ValueError): audit(root)

    def test_response_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, relative='elsewhere.html.gz')
            with self.assertRaises(ValueError): audit(root)

    def test_nonofficial_or_unobserved_target_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, url='https://example.org/history.html')
            self.assertEqual(audit(root)['source_versions'], 0)
