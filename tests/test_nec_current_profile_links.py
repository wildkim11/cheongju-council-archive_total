import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from link_nec_current_profiles import career_match, reconcile, build
from audit_nec_election_samples import build_current

ROOT = Path(__file__).resolve().parents[1]


class CurrentProfileLinkTests(unittest.TestCase):
    def fixture(self):
        profile = {'profile_id': 'synthetic-A', 'name': '시험인', 'careers': ['전) 중국 장춘공업대학 인문정보학원 교수']}
        for k in ('source_url','source_manifest','manifest_sha256','source_response_path','decoded_utf8_sha256','career_section_sha256'): profile[k]='synthetic-' + k
        roster = {('시험인', profile['source_url']): [{'parsed_row': {'district': '사선거구'}}]}
        anchor = {'query_name': '시험인', 'target_local_council_scope': True, 'election_date': '2026-06-03',
                  'displayed_heading': '[2026.06.03] 제9회 전국동시지방선거 / 충청북도(청주시사선거구)',
                  'displayed_municipality': '청주시', 'winner_tab_and_badge_confirmed': True,
                  'nec_person_group_id': 'synthetic-nec-A', 'event_id': 'synthetic-win-2026',
                  'source_url': 'synthetic-NEC-url', 'source_response_path': 'synthetic-NEC-path',
                  'source_response_sha256': 'synthetic-NEC-sha', 'source_spans': [],
                  'published_profile_facts': [{'tab': '당선인', 'field': '경력', 'text': '(전)중국 장춘공업대학 인문정보학원 교수'}]}
        earlier = {**anchor, 'event_id': 'synthetic-win-2018', 'election_date': '2018-06-13'}
        audit = {'sources': [{'query_name': '시험인', 'parse_status': 'VERIFIED_SOURCE'}], 'events': [anchor, earlier]}
        return {'rows': [profile]}, roster, audit

    def test_full_phrase_and_local_prefix_match_but_generic_roles_do_not(self):
        self.assertTrue(career_match('전) 상당구 주민복지과장', '(전)청주시 상당구 주민복지과장'))
        self.assertFalse(career_match('전) 제3대 청주시의회 의원', '(전)제3대 청주시의회 의원'))
        self.assertFalse(career_match('전) 위원장', '(전)위원장'))
        self.assertFalse(career_match('전) 장춘공업대학 교수', '(전)다른장춘공업대학 교수'))

    def test_noncontinuous_wins_count_as_observed_lower_bound_without_exact_seniority(self):
        row = reconcile(*self.fixture())[0]
        self.assertTrue(row['election_event_link_usable'])
        self.assertEqual(row['observed_win_count_lower_bound'], 2)
        self.assertTrue(row['geographic_two_win_filter_match'])
        self.assertIsNone(row['seniority_exact'])
        self.assertFalse(row['complete_election_history_verified'])
        self.assertFalse(row['canonical_identity_merge'])

    def test_single_observed_win_is_unknown_for_reelection_not_false(self):
        careers, roster, audit = self.fixture(); audit['events'] = audit['events'][:1]
        row = reconcile(careers, roster, audit)[0]
        self.assertEqual(row['observed_win_count_lower_bound'], 1)
        self.assertIsNone(row['geographic_two_win_filter_match'])
        self.assertIsNone(row['seniority_exact'])

    def test_name_district_anchor_and_independent_career_all_required(self):
        for kind in ('name','district','date','badge','career'):
            careers, roster, audit = self.fixture()
            if kind=='name': audit['events'][0]['query_name']='다른사람'
            if kind=='district': next(iter(roster.values()))[0]['parsed_row']['district']='다선거구'
            if kind=='date': audit['events'][0]['election_date']='2022-06-01'
            if kind=='badge': audit['events'][0]['winner_tab_and_badge_confirmed']=False
            if kind=='career': audit['events'][0]['published_profile_facts']=[]
            row = reconcile(careers, roster, audit)[0]
            self.assertFalse(row['election_event_link_usable'], kind)
            self.assertIsNone(row['geographic_two_win_filter_match'])

    def test_multiple_matching_groups_or_districts_held(self):
        careers, roster, audit = self.fixture()
        another = copy.deepcopy(audit['events'][0]); another['nec_person_group_id']='other-person'; another['event_id']='other'
        audit['events'].append(another)
        self.assertFalse(reconcile(careers, roster, audit)[0]['election_event_link_usable'])
        careers, roster, audit = self.fixture()
        next(iter(roster.values())).append({'parsed_row': {'district': '다선거구'}})
        self.assertFalse(reconcile(careers, roster, audit)[0]['election_event_link_usable'])

    def test_duplicate_event_ids_never_double_count(self):
        careers, roster, audit = self.fixture()
        audit['events'].append(copy.deepcopy(audit['events'][1]))
        self.assertEqual(reconcile(careers, roster, audit)[0]['observed_win_count_lower_bound'], 2)

    def test_actual_roster_queries_and_profile_links_are_partial_not_full_seniority(self):
        audit = build_current(ROOT, write=False)
        self.assertEqual(len(audit['sources']), 44)
        self.assertEqual(audit['parsed_sources'], 44)
        self.assertEqual(audit['held_sources'], 0)
        self.assertEqual(audit['target_local_council_events'], 83)
        self.assertEqual(audit['target_local_council_wins'], 75)
        links = build(ROOT, write=False)
        self.assertEqual(links['source_corroborated_event_links'], 19)
        self.assertEqual(links['held_profiles'], 25)
        self.assertEqual(links['geographic_two_win_filter_true'], 6)
        self.assertEqual(links['geographic_two_win_filter_unknown'], 38)
        self.assertEqual(links['exact_seniorities_confirmed'], 0)
        self.assertEqual(links['canonical_identity_merges'], 0)
