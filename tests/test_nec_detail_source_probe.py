import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import probe_nec_detail_sources as p


class DetailProbeTests(unittest.TestCase):
    def menu(self):
        return {'menu_id': 'BIAP01', 'menu_id_discrepancy': False,
            'observed_url': 'https://info.nec.go.kr/main/showDocument.xhtml?electionId=0020260603&topMenuId=BI&secondMenuId=BIAP01',
            'selector_names': ['cityCode', 'townCode'], 'enclosing_data_attributes':
            {'data-election-code': '6', 'data-city-code': '4300', 'data-town-code': '4301', 'data-election-name': '20260603'}}

    def planned(self):
        return [{'menu_id': m, 'url': 'https://info.nec.go.kr/synthetic?menu=' + m} for m in p.MENUS]

    def test_only_reviewed_2026_chungbuk_municipal_transport_supported(self):
        self.assertTrue(p.detail_url(self.menu()).endswith('searchAction=true&cityCode=4300&townCode=4301'))
        for change in ('host', 'election', 'kind', 'city', 'menu', 'selector', 'conflict'):
            m = self.menu()
            if change == 'host': m['observed_url'] = m['observed_url'].replace('info.nec.go.kr', 'other.invalid')
            if change == 'election': m['observed_url'] = m['observed_url'].replace('0020260603', '0000000000')
            if change == 'kind': m['enclosing_data_attributes']['data-election-code'] = '5'
            if change == 'city': m['enclosing_data_attributes']['data-city-code'] = '1'
            if change == 'menu': m['menu_id'] = 'CPRI06'
            if change == 'selector': m['selector_names'] = ['searchType']
            if change == 'conflict': m['menu_id_discrepancy'] = True
            with self.assertRaises(ValueError): p.detail_url(m)

    def test_unknown_or_changed_inline_transport_is_rejected(self):
        for text in ('nothing', 'function fn_searchSelect(x){} /* 생년월일 */'):
            with self.assertRaises(ValueError): p.transport_evidence(text)

    def test_inventory_does_not_treat_table_presence_as_verified_results(self):
        r = p.inventory(b'<html><title>sample</title><table><tr><td>placeholder</td></tr></table><select id="x"><option value="0">all</option></select></html>')
        self.assertEqual(r['table_count'], 1)
        self.assertFalse(r['result_extraction_verified'])
        self.assertEqual(r['selects'][0]['options'][0]['value'], '0')

    def test_runtime_guard_makes_no_requests(self):
        calls = []
        with self.assertRaises(ValueError): p.collect(request=lambda *a, **kw: calls.append(a), system=lambda: 'Linux')
        self.assertFalse(calls)

    def test_six_pages_reuse_verified_bytes_without_new_requests(self):
        with tempfile.TemporaryDirectory() as td, patch.object(p, 'targets', return_value=self.planned()):
            calls = []
            def request(url, **kw):
                calls.append(url); return ('<html><title>' + url + '</title></html>').encode()
            r = p.collect(td, request=request, system=lambda: 'Darwin', pause=lambda _: None)
            self.assertEqual(r['requests_this_run'], 6)
            self.assertFalse(r['complete_district_results'])
            r = p.collect(td, request=request, system=lambda: 'Darwin', pause=lambda _: None)
            self.assertEqual(r['requests_this_run'], 0)
            self.assertEqual(r['reused_verified_sources'], 6)
            self.assertEqual(len(calls), 6)

    def test_source_error_stops_without_retry_and_distinguishes_unattempted(self):
        with tempfile.TemporaryDirectory() as td, patch.object(p, 'targets', return_value=self.planned()):
            calls = []
            def request(url, **kw): calls.append(url); raise OSError('synthetic failure')
            r = p.collect(td, request=request, system=lambda: 'Darwin', pause=lambda _: None)
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(r['errors']), 1)
            self.assertEqual(len(r['unattempted_menu_ids']), 5)
            self.assertEqual(r['status'], 'INCOMPLETE')

    def test_tampered_cached_source_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as td, patch.object(p, 'targets', return_value=self.planned()):
            r = p.collect(td, request=lambda *a, **kw: b'<html>sample</html>', system=lambda: 'Darwin', pause=lambda _: None)
            (Path(td) / r['sources'][0]['path']).write_bytes(b'invalid-gzip')
            calls = []
            r = p.collect(td, request=lambda *a, **kw: calls.append(a), system=lambda: 'Darwin')
            self.assertFalse(calls); self.assertEqual(r['status'], 'INCOMPLETE')

    def test_actual_six_menus_come_from_pinned_preserved_source(self):
        rows = p.targets(p.ROOT)
        self.assertEqual([r['menu_id'] for r in rows], list(p.MENUS))
        self.assertTrue(all(r['inline_transport']['span_sha256'] == p.TRANSPORT_SHA for r in rows))
        self.assertTrue(all('searchAction=true' in r['url'] for r in rows))


if __name__ == '__main__': unittest.main()
