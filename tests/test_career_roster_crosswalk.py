import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_career_roster_crosswalk import parse_claim, crosswalk, build


class CareerRosterCrosswalkTests(unittest.TestCase):
    def fixture(self, quotes):
        people = [{'person_id': 'current', 'name': '시험인', 'official_profile_url': 'https://council.cheongju.go.kr/memberHome/content/profile.html?f_code=A1'},
                  {'person_id': 'historical', 'name': '시험인', 'official_profile_url': 'https://council.cheongju.go.kr/include/memberProfile.html?daesu=2&mcode=A1'}]
        tenures = [{'person_id': 'current', 'term': 4, 'council_scope': 'cheongju_integrated'},
                   {'person_id': 'historical', 'term': 2, 'council_scope': 'cheongju_integrated'}]
        source = {k: 'synthetic' for k in ('source_url', 'source_manifest', 'manifest_sha256', 'source_response_path', 'decoded_utf8_sha256', 'career_section_sha256')}
        careers = {'rows': [{**source, 'profile_id': 'current', 'name': '시험인', 'careers': quotes, 'numbered_council_career_mentions': quotes}]}
        historical = {(2, people[1]['official_profile_url'], '시험인'): [{'source_response_path': 'synthetic historical response'}]}
        current = {('시험인', people[0]['official_profile_url']): [{'source_response_path': 'synthetic current response'}]}
        return careers, people, tenures, historical, current

    def test_explicit_term_enumerations_not_committee_cohorts(self):
        self.assertEqual(parse_claim('전) 제2대, 3대 청주시의회 농업정책위원장')['terms'], [2, 3])
        self.assertEqual(parse_claim('전) 제1, 3대 청주시의회 의원')['terms'], [1, 3])
        self.assertEqual(parse_claim('전) 제3대 청주시의회 예산결산특별위원장(제1,3기)')['terms'], [3])

    def test_range_duplicate_unlabelled_or_multiple_expressions_held(self):
        for text in ['전) 제1~3대 청주시의회 의원', '전) 제2,2대 청주시의회 의원',
                     '제2대 청주시의회 의원', '전) 제2대 청주시의회 의원, 제3대 청주시의회 의원']:
            with self.subTest(text=text): self.assertEqual(parse_claim(text)['status'], 'HELD')

    def test_noncontinuous_candidate_terms_not_losses_or_seniority(self):
        mentions, groups, profiles = crosswalk(*self.fixture(['전) 제2대 청주시의회 의원']))
        self.assertEqual(profiles[0]['source_backed_candidate_terms'], [2, 4])
        self.assertEqual(profiles[0]['unobserved_terms_between_mentions'], [3])
        self.assertFalse(profiles[0]['unobserved_terms_are_losses'])
        self.assertIsNone(profiles[0]['seniority'])
        self.assertFalse(groups[0]['analysis_identity_usable'])
        self.assertFalse(mentions[0]['election_fact'])

    def test_repeated_offices_deduplicate_profile_term_candidate(self):
        _, groups, _ = crosswalk(*self.fixture(['전) 제2대 청주시의회 의원', '전) 제2대 청주시의회 예산결산특별위원장']))
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]['career_mentions']), 2)

    def test_same_name_without_reparsed_roster_is_held(self):
        args = list(self.fixture(['전) 제2대 청주시의회 의원'])); args[3] = {}
        _, groups, _ = crosswalk(*args)
        self.assertEqual(groups[0]['status'], 'HELD_NO_REPARSED_ROSTER_RESPONSE')
        self.assertIsNone(groups[0]['canonical_person_id'])

    def test_multiple_same_name_or_scope_candidates_remain_ambiguous(self):
        args = list(self.fixture(['전) 제2대 청주시의회 의원']))
        args[1].append({'person_id': 'old', 'name': '시험인', 'official_profile_url': 'https://council.cheongju.go.kr/old/profile'})
        args[2].append({'person_id': 'old', 'term': 2, 'council_scope': 'cheongju_old_city'})
        mentions, _, _ = crosswalk(*args)
        self.assertEqual(mentions[0]['candidates_by_term'][0]['status'], 'AMBIGUOUS_MULTIPLE_ROSTER_CANDIDATES')
        args[0]['rows'][0]['careers'] = args[0]['rows'][0]['numbered_council_career_mentions'] = ['전) 통합 제2대 청주시의회 의원']
        mentions, _, _ = crosswalk(*args)
        self.assertEqual(len(mentions[0]['candidates_by_term'][0]['candidates']), 1)

    def test_missing_career_is_not_first_term_or_zero(self):
        _, _, profiles = crosswalk(*self.fixture([]))
        self.assertEqual(profiles[0]['source_backed_candidate_terms'], [4])
        self.assertIsNone(profiles[0]['seniority'])
        self.assertFalse(profiles[0]['complete_career_verified'])

    def test_duplicate_profile_or_missing_tenure_profile_fails(self):
        args = list(self.fixture([])); args[1].append(copy.deepcopy(args[1][0]))
        with self.assertRaises(ValueError): crosswalk(*args)
        args = list(self.fixture([])); args[2][0]['person_id'] = 'missing'
        with self.assertRaises(ValueError): crosswalk(*args)

    def test_actual_career_mentions_source_backed_without_promotion(self):
        result = build(Path(__file__).resolve().parents[1], write=False)
        self.assertEqual(result['career_mentions'], 69)
        self.assertEqual(result['expanded_term_mentions'], 70)
        self.assertEqual(result['profile_term_candidates'], 51)
        self.assertEqual(result['source_backed_profile_term_candidates'], 51)
        self.assertEqual(result['profiles_with_noncontinuous_mentions'], 1)
        self.assertEqual(result['seniority_decisions'], 0)
        self.assertEqual(result['canonical_identity_merges'], 0)
        self.assertEqual(result['official_election_facts'], 0)
