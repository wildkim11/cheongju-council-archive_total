from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_nec_report_samples as p


class ReportSampleTests(unittest.TestCase):
    def form(self):
        values = {'electionId': '0020260603', 'requestURI': '/electioninfo/0020260603/bi/biap01.jsp',
                  'menuId': 'BIAP01', 'secondMenuId': 'BIAP01', 'statementId': 'BIAP01'}
        return '<html><form id="searchForm" method="post" action="/electioninfo/electionInfo_report.xhtml">' + ''.join(
            '<input type="hidden" name="'+k+'" value="'+v+'">' for k, v in values.items()) + '''<select name="cityCode"><option value="-1" selected>choose</option><option value="4300" selected>region</option></select><select name="townCode"><option value="4301">town</option></select><input type="checkbox" name="unchecked" value="1"><input name="disabled" disabled><input type="submit" name="submit"></form></html>'''

    def test_successful_controls_and_single_select_last_selected_are_preserved(self):
        r = p.form_contract(self.form(), 'BIAP01')
        self.assertEqual(dict(r['form_pairs'])['cityCode'], '4300')
        self.assertNotIn('unchecked', dict(r['form_pairs']))
        self.assertNotIn('disabled', dict(r['form_pairs']))
        self.assertNotIn('submit', dict(r['form_pairs']))
        self.assertEqual(len(r['selector_notes']), 1)

    def test_changed_scope_destination_request_uri_or_duplicate_fields_rejected(self):
        for text in (self.form().replace('0020260603', '0000000000'),
                     self.form().replace('/electioninfo/electionInfo_report.xhtml', 'https://other.invalid/query'),
                     self.form().replace('/bi/biap01.jsp', '/else.jsp'),
                     self.form().replace('</form>', '<input name="cityCode" value="4300"></form>')):
            with self.assertRaises(ValueError): p.form_contract(text, 'BIAP01')

    def test_post_destination_guard_precedes_network(self):
        with self.assertRaises(ValueError): p.post_report('https://other.invalid/', [])

    def test_non_macos_guard_precedes_network(self):
        with self.assertRaises(ValueError): p.collect(system=lambda: 'Linux')

    def test_error_stops_without_retry_and_keeps_unattempted_separate(self):
        planned = [{'menu_id': m, 'url': p.URL, 'form_pairs': []} for m in p.MENUS]
        with tempfile.TemporaryDirectory() as td, patch.object(p, 'plans', return_value=planned):
            calls = []
            def request(*args): calls.append(args); raise OSError('synthetic')
            r = p.collect(td, request=request, system=lambda: 'Darwin')
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(r['unattempted_menu_ids']), 2)
            self.assertFalse(r['complete_district_results'])

    def test_actual_three_forms_preserve_verified_source_and_statement_choice(self):
        rows = p.plans(p.ROOT)
        self.assertEqual([r['menu_id'] for r in rows], list(p.MENUS))
        self.assertEqual([dict(r['form_pairs'])['statementId'] for r in rows], ['BIAP01','CPRI03_#6','VCCP08_#00'])


if __name__ == '__main__': unittest.main()
