import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_nec_election_ledger import heading_fields, source_menus, assemble, build
from audit_nec_election_samples import sha

ROOT = Path(__file__).resolve().parents[1]


class ElectionLedgerTests(unittest.TestCase):
    def heading(self, metrics=' / 1,234표 (12.30%) 당선', kind='구·시·군의회의원선거'):
        return '[2026.06.03] 제9회 전국동시지방선거 정당 / ' + kind + ' / 충청북도(청주시가선거구)' + metrics

    def fixture(self):
        text = '''<div class="list" data-election-code="6"><a onclick="fn_searchSelect(this,'main/showDocument.xhtml?electionId=0020260603&amp;topMenuId=CP&amp;secondMenuId=CPRI03','cityCode,townCode','CPRI03');">후보자명부</a></div>'''
        event = {'event_id': 'synthetic-event', 'query_name': '시험인', 'nec_person_group_id': 'synthetic-group',
                 'election_date': '2026-06-03', 'target_local_council_scope': True,
                 'winner_tab_and_badge_confirmed': False, 'displayed_heading': self.heading(),
                 'codes': {'election-code': '6'}, 'source_response_path': 'synthetic-path',
                 'source_response_sha256': sha(text.encode()), 'source_url': 'synthetic-url',
                 'source_spans': [{'char_start': 0, 'char_end': len(text), 'span_sha256': sha(text.encode()), 'tab': '후보자'}]}
        return text, event

    def test_displayed_votes_and_decimal_precision_are_preserved(self):
        r = heading_fields(self.heading())
        self.assertEqual(r['displayed_vote_count'], 1234)
        self.assertEqual(r['displayed_vote_share_percent'], '12.30')
        self.assertIsNone(r['vote_share_denominator'])
        self.assertIsNone(r['calculated_vote_share_percent'])

    def test_missing_is_not_zero_and_does_not_imply_uncontested(self):
        r = heading_fields(self.heading('당선'))
        self.assertIsNone(r['displayed_vote_count'])
        self.assertEqual(r['uncontested_status'], 'UNVERIFIED')
        self.assertEqual(r['metrics_status'], 'NOT_DISPLAYED')
        zero = heading_fields(self.heading(' / 0표 (0.00%)'))
        self.assertEqual(zero['displayed_vote_count'], 0)

    def test_invalid_vote_grouping_percentage_or_shape_is_rejected(self):
        for suffix in (' / 12,34표 (1%)', ' / 1표 (100.01%)', ' / -1표 (0%)', ' / 12표', ' / 00표 (0%)', ' / 2표 (NaN%)'):
            with self.assertRaises(ValueError): heading_fields(self.heading(suffix))

    def test_proportional_metrics_never_become_personal_votes(self):
        r = heading_fields(self.heading(kind='기초의원비례대표선거'))
        self.assertEqual(r['representation'], 'proportional')
        self.assertFalse(r['personal_vote_comparison_usable'])

    def test_menu_is_literal_observation_with_exact_original_spans(self):
        text, event = self.fixture()
        m = source_menus(text, event)[0]
        self.assertEqual(m['selector_names'], ['cityCode', 'townCode'])
        self.assertFalse(m['transport_verified'])
        self.assertEqual(sha(text[m['char_start']:m['char_end']].encode()), m['span_sha256'])
        self.assertFalse(m['menu_id_discrepancy'])

    def test_observed_menu_id_discrepancy_preserved_without_fixing_source(self):
        text, event = self.fixture()
        text = text.replace("'CPRI03');", "'BIGO06');")
        event['source_spans'][0].update(char_end=len(text), span_sha256=sha(text.encode()))
        m = source_menus(text, event)[0]
        self.assertTrue(m['menu_id_discrepancy'])
        self.assertEqual(m['url_menu_id'], 'CPRI03')
        self.assertEqual(m['menu_id'], 'BIGO06')

    def test_menu_source_tampering_or_external_destination_rejected(self):
        text, event = self.fixture()
        with self.assertRaises(ValueError): source_menus(text.replace('후보자', '다른'), event)
        for url in ('https://other.invalid/main/showDocument.xhtml', 'https://info.nec.go.kr/other.xhtml'):
            changed = text.replace('main/showDocument.xhtml', url)
            e = copy.deepcopy(event)
            e['source_spans'][0].update(char_end=len(changed), span_sha256=sha(changed.encode()))
            with self.assertRaises(ValueError): source_menus(changed, e)

    def test_candidate_only_is_not_loss_or_current_identity_even_if_heading_has_badge(self):
        text, event = self.fixture()
        rows, held, targets, review = assemble({'events': [event]}, {'rows': []}, {'rows': []}, {'synthetic-path': text})
        r = rows[0]
        self.assertEqual(r['result_status'], 'CANDIDACY_WITHOUT_CONFIRMED_RESULT')
        self.assertIsNone(r['current_profile_id'])
        self.assertFalse(r['current_profile_comparison_usable'])
        for key in ('rank', 'seat_count', 'candidate_count', 'electoral_margin_votes', 'council_term'):
            self.assertIsNone(r[key])
        self.assertFalse(r['district_complete'])

    def test_same_menu_contract_reused_with_all_event_evidence(self):
        text, event = self.fixture(); other = {**event, 'event_id': 'synthetic-other'}
        rows, held, targets, _ = assemble({'events': [event, other]}, {'rows': []}, {'rows': []}, {'synthetic-path': text})
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(targets), 1)
        self.assertEqual(len(targets[0]['source_event_ids']), 2)
        self.assertEqual(targets[0]['transport_status'], 'OBSERVED_MENU_ONLY_NOT_REQUEST_READY')

    def test_unsupported_event_is_held_without_suppressing_other_events(self):
        text, event = self.fixture(); other = {**event, 'event_id': 'held', 'displayed_heading': 'changed format'}
        rows, held, _, _ = assemble({'events': [event, other]}, {'rows': []}, {'rows': []}, {'synthetic-path': text})
        self.assertEqual(len(rows), 1); self.assertEqual(len(held), 1)

    def test_actual_preserved_sources_keep_coverage_and_identity_limits(self):
        r = build(ROOT, write=False)
        self.assertEqual(r['source_target_events'], 83)
        self.assertEqual(r['parsed_observations'], 83)
        self.assertEqual(r['held_observations'], 0)
        self.assertEqual(r['displayed_vote_observations'], 67)
        self.assertEqual(r['missing_displayed_metrics'], 16)
        self.assertEqual(r['identity_linked_observations'], 30)
        self.assertEqual(r['held_current_profiles'], 25)
        self.assertEqual(r['ranks_calculated'], 0)
        self.assertEqual(r['complete_districts'], 0)
        self.assertEqual(r['official_site_requests'], 0)
        self.assertNotIn('data-birthday', json.dumps(r))


if __name__ == '__main__':
    unittest.main()
