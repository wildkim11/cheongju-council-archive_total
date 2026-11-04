import gzip
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from probe_nec_election_sources import inspect, URL


class NECSourceInspectionTests(unittest.TestCase):
    def test_platform_guard_precedes_requests(self):
        calls = []
        with self.assertRaises(ValueError): inspect(request=lambda u: calls.append(u), system=lambda: 'Linux')
        self.assertEqual(calls, [])

    def test_only_observed_same_host_search_scripts_up_to_three_gets(self):
        with tempfile.TemporaryDirectory() as temp, patch('probe_nec_election_sources.time.sleep'):
            calls = []
            def request(url):
                calls.append(url)
                if url == URL:
                    return b'<script src="/js/search.js"></script><script src="https://example.org/search.js"></script><script src="/js/candidate.js"></script><script src="/js/search-more.js"></script>'
                return b'// read only'
            r = inspect(temp, request=request, system=lambda: 'Darwin')
            self.assertEqual(len(calls), 3)
            self.assertTrue(all(u.startswith('https://info.nec.go.kr/') for u in calls))
            self.assertEqual(r['election_rows_collected'], 0)
            for source in r['sources']:
                self.assertEqual(len(gzip.decompress((Path(temp) / source['path']).read_bytes())), source['bytes'])

    def test_first_transport_error_stops_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            calls = []
            def request(url):
                calls.append(url); raise OSError('unavailable')
            r = inspect(temp, request=request, system=lambda: 'Darwin')
            self.assertEqual(calls, [URL])
            self.assertEqual(r['status'], 'INCOMPLETE')
