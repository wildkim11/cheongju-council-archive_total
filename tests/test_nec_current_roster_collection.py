import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_nec_current_roster import collect, verify_source, LIMIT
from process_meeting_segments import sha


class CurrentRosterCollectionTests(unittest.TestCase):
    def fixtures(self, root):
        rows = [{'profile_id': 'synthetic-' + str(i), 'name': chr(0xac00+i) + '시험', 'source_url': 'https://example.invalid/' + str(i)} for i in range(44)]
        stack = []
        for target, value in [('verify_transport', None), ('career_evidence', {'rows': rows}), ('current_rosters', {(r['name'], r['source_url']): [{}] for r in rows})]:
            mock = patch('collect_nec_current_roster.' + target, return_value=value); mock.start(); self.addCleanup(mock.stop)
        return rows

    def test_platform_guard_before_files_or_requests(self):
        calls = []
        with self.assertRaises(ValueError): collect(request=lambda u: calls.append(u), system=lambda: 'Linux')
        self.assertEqual(calls, [])

    def test_each_target_at_most_once_and_second_run_reuses_all(self):
        with tempfile.TemporaryDirectory() as temp, patch('collect_nec_current_roster.time.sleep'):
            root = Path(temp); self.fixtures(root); calls = []
            def request(url): calls.append(url); return '<html>합성검색</html>'.encode()
            result = collect(root, request=request, system=lambda: 'Darwin')
            self.assertEqual(result['official_requests_attempted'], 44)
            self.assertEqual(len(set(calls)), 44)
            result = collect(root, request=lambda u: self.fail('preserved source queried again'), system=lambda: 'Darwin')
            self.assertEqual(result['official_requests_attempted'], 0)
            self.assertEqual(result['reused_preserved_sources'], 44)

    def test_three_consecutive_errors_stop_remaining_requests(self):
        with tempfile.TemporaryDirectory() as temp, patch('collect_nec_current_roster.time.sleep'):
            root = Path(temp); self.fixtures(root); calls = []
            def request(url): calls.append(url); raise OSError('source unavailable')
            result = collect(root, request=request, system=lambda: 'Darwin')
            self.assertEqual(len(calls), 3)
            self.assertEqual(len(result['unattempted_profiles']), 41)
            self.assertEqual(result['status'], 'PARTIAL')

    def test_cached_source_tamper_is_not_silently_requeried(self):
        with tempfile.TemporaryDirectory() as temp, patch('collect_nec_current_roster.time.sleep'):
            root = Path(temp); self.fixtures(root)
            result = collect(root, request=lambda u: b'<html>synthetic</html>', system=lambda: 'Darwin')
            path = root / result['sources'][0]['path']; path.write_bytes(gzip.compress(b'tampered'))
            with self.assertRaises(ValueError): collect(root, request=lambda u: self.fail('no HTTP after hash failure'), system=lambda: 'Darwin')
