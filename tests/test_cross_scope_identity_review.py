import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_cross_scope_identity_review as b


class CrossScopeReviewTests(unittest.TestCase):
    def fixture(self,occurrences):
        people=[];tenures=[]
        for i,(scope,term) in enumerate(occurrences):
            pid='synthetic-'+str(i)
            people.append({'person_id':pid,'name':'시험인','official_profile_url':None})
            tenures.append({'person_id':pid,'council_scope':scope,'term':term})
        return people,tenures

    def test_integrated_four_terms_and_legacy_records_share_review_not_identity(self):
        p,t=self.fixture([('cheongju_old_city',8),('cheongju_old_city',9)]+[('cheongju_integrated',i) for i in range(1,5)])
        with tempfile.TemporaryDirectory() as td:g=b.assemble(td,p,t)[0]
        self.assertTrue(g['legacy_to_integrated_review'])
        self.assertTrue(g['integrated_1_to_4_candidate_presence'])
        self.assertEqual(len(g['profiles']),6)
        self.assertEqual(len(g['profile_pair_candidates']),15)
        self.assertIsNone(g['canonical_person_id']);self.assertIsNone(g['seniority_exact'])
        self.assertIsNone(g['verified_person_continuity'])

    def test_scope_numbering_reset_never_creates_losses_or_cross_scope_gap(self):
        p,t=self.fixture([('cheongju_old_city',9),('cheongju_integrated',1),('cheongju_integrated',3)])
        with tempfile.TemporaryDirectory() as td:g=b.assemble(td,p,t)[0]
        lanes={r['council_scope']:r for r in g['scope_lanes']}
        self.assertEqual(lanes['cheongju_old_city']['unobserved_term_numbers_between'],[])
        self.assertEqual(lanes['cheongju_integrated']['unobserved_term_numbers_between'],[2])
        self.assertFalse(lanes['cheongju_integrated']['missing_terms_are_losses'])
        self.assertFalse(g['council_number_reset_is_career_reset'])

    def test_city_county_homonyms_remain_unapproved(self):
        p,t=self.fixture([('cheongju_old_city',1),('cheongwon_old_county',1)])
        with tempfile.TemporaryDirectory() as td:g=b.assemble(td,p,t)[0]
        self.assertTrue(g['cross_scope_review']);self.assertFalse(g['legacy_to_integrated_review'])
        self.assertFalse(g['profile_pair_candidates'][0]['identity_approved'])

    def test_same_scope_term_duplicate_profiles_are_visible_review_conflicts(self):
        p,t=self.fixture([('cheongju_integrated',1),('cheongju_integrated',1)])
        with tempfile.TemporaryDirectory() as td:g=b.assemble(td,p,t)[0]
        pair=g['profile_pair_candidates'][0]
        self.assertEqual(pair['same_scope_term_multiple_profiles'],[{'council_scope':'cheongju_integrated','term':1}])
        self.assertFalse(pair['analysis_identity_usable'])

    def test_matching_portraits_and_valid_codes_never_approve_or_merge(self):
        p,t=self.fixture([('cheongju_integrated',1),('cheongju_integrated',2)])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/'archive/people/portraits/synthetic.jpg';path.parent.mkdir(parents=True);path.write_bytes(b'synthetic portrait bytes')
            for person,tenure in zip(p,t):
                person.update(official_profile_code='a',official_profile_code_type='mcode',
                    official_profile_url='https://council.cheongju.go.kr/include/memberProfile.html?mcode=a&daesu='+str(tenure['term']),
                    portrait={'local_path':'archive/people/portraits/synthetic.jpg','sha256':b.sha(path.read_bytes())})
            g=b.assemble(root,p,t)[0];pair=g['profile_pair_candidates'][0]
            self.assertTrue(pair['same_verified_portrait_bytes']);self.assertTrue(pair['shared_qualified_code_keys'])
            self.assertFalse(pair['identity_approved']);self.assertEqual(g['automatic_identity_merges'],0)
            path.write_bytes(b'tampered')
            with self.assertRaises(ValueError):b.assemble(root,p,t)

    def test_missing_personal_dates_are_not_filled_from_council_terms(self):
        p,t=self.fixture([('cheongju_integrated',1),('cheongju_integrated',2)])
        with tempfile.TemporaryDirectory() as td:g=b.assemble(td,p,t)[0]
        self.assertTrue(all(o['explicit_personal_interval'] is None for m in g['profiles'] for o in m['occurrences']))

    def test_bad_scope_or_unknown_profile_references_rejected(self):
        p,t=self.fixture([('cheongju_integrated',1),('cheongju_integrated',2)])
        for kind in ('scope','term','person'):
            v=copy.deepcopy(t)
            if kind=='scope':v[0]['council_scope']='unqualified_city'
            if kind=='term':v[0]['term']=True
            if kind=='person':v[0]['person_id']='missing'
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError):b.assemble(td,p,v)

    def test_actual_records_cover_cross_scope_and_four_term_candidates_without_promotion(self):
        r=b.build(write=False)
        self.assertEqual(r['profile_rows'],435)
        self.assertEqual(r['name_review_groups'],115)
        self.assertEqual(r['profile_pair_candidates'],259)
        self.assertEqual(r['cross_scope_review_groups'],21)
        self.assertEqual(r['legacy_to_integrated_review_groups'],20)
        self.assertEqual(r['integrated_1_to_4_candidate_name_groups'],4)
        self.assertEqual(r['canonical_identity_merges'],0)
        self.assertEqual(r['seniority_decisions'],0)


if __name__=='__main__':unittest.main()
