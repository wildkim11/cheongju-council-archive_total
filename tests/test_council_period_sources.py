import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_council_period_sources import collect, request, TARGETS


class PeriodSourceTests(unittest.TestCase):
    def test_linux_rejected_before_request(self):
        with tempfile.TemporaryDirectory() as root:
            calls = []
            with self.assertRaises(ValueError):
                collect(root, fetch=lambda t: calls.append(t), system=lambda: 'Linux')
            self.assertEqual(calls, [])

    def test_three_exact_sources_saved_without_promotion(self):
        with tempfile.TemporaryDirectory() as root, patch('collect_council_period_sources.time.sleep'):
            calls = []
            def fetch(t):
                calls.append(t)
                return '<html>한글 ' + t + '</html>'
            report = collect(root, fetch=fetch, system=lambda: 'Darwin')
            self.assertEqual(calls, list(TARGETS))
            self.assertEqual(report['official_periods_promoted'], 0)
            manifest = json.loads((Path(root) / report['source_manifest']).read_text())
            for row in manifest['responses']:
                raw = gzip.decompress((Path(root) / row['path']).read_bytes())
                self.assertEqual(len(raw), row['bytes'])
                self.assertIn('한글', raw.decode())

    def test_stop_on_first_error_no_retry(self):
        with tempfile.TemporaryDirectory() as root:
            calls = []
            def fetch(t):
                calls.append(t)
                raise OSError('source unavailable')
            report = collect(root, fetch=fetch, system=lambda: 'Darwin')
            self.assertEqual(calls, [TARGETS[0]])
            self.assertEqual(report['status'], 'INCOMPLETE')
            self.assertEqual(len(report['failures']), 1)

    def test_arbitrary_url_rejected(self):
        with self.assertRaises(ValueError):
            request('/content/unobserved.html')

    def test_existing_bad_content_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root, patch('collect_council_period_sources.time.sleep'):
            fetch = lambda t: '<html>한글</html>'
            report = collect(root, fetch=fetch, system=lambda: 'Darwin')
            manifest = json.loads((Path(root) / report['source_manifest']).read_text())
            path = Path(root) / manifest['responses'][0]['path']
            path.write_bytes(gzip.compress(b'tampered'))
            report = collect(root, fetch=fetch, system=lambda: 'Darwin')
            self.assertEqual(report['status'], 'INCOMPLETE')
            self.assertEqual(gzip.decompress(path.read_bytes()), b'tampered')
