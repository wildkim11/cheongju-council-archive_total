import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_nec_city_election as a
import collect_nec_city_election as c


class CityAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=a.build(write=False)
        cls.manifest=json.loads((c.ROOT/c.REPORT).read_text())
        cls.by={s['target_id']:s for s in cls.manifest['sources']}

    def copy_sources(self,root):
        for folder in ('detail_responses','report_responses','city_responses'):
            shutil.copytree(c.ROOT/'archive/elections/nec'/folder,root/'archive/elections/nec'/folder)
        (root/'reports').mkdir()
        for name in ('nec-city-election-collection-latest.json','nec-detail-source-probe-latest.json','nec-report-samples-latest.json'):
            shutil.copy2(c.ROOT/'reports'/name,root/'reports'/name)

    def test_four_committee_facilities_and_fourteen_rosters_match_captured_scope(self):
        r=self.report
        self.assertEqual(r['facility_committees_verified'],4)
        self.assertEqual(r['polling_place_rows'],43)
        self.assertEqual(r['candidate_districts_verified'],14)
        self.assertEqual(r['candidate_rows'],64)
        self.assertTrue(r['whole_city_facility_tables_verified'])
        self.assertFalse(r['whole_city_election_results_verified'])

    def test_twelve_count_tables_and_two_explicit_uncontested_reports_account_for_all(self):
        r=self.report
        self.assertEqual(r['count_districts_verified'],12)
        self.assertEqual(r['officially_uncontested_districts'],2)
        self.assertEqual(r['count_districts_held'],0)
        self.assertEqual(r['count_unit_rows'],156)
        self.assertTrue(r['all_district_count_reports_accounted'])
        for d in r['districts']:
            if d['count_status']=='SOURCE_DECLARED_UNCONTESTED':
                self.assertIsNone(d['count_units'])
                self.assertEqual(d['count_metrics_status'],'NOT_APPLICABLE_UNCONTESTED')
                self.assertFalse(d['winners_verified']);self.assertFalse(d['seats_verified'])

    def test_navigation_text_never_substitutes_for_uncontested_report_body(self):
        key=next(d['count_source_target_id'] for d in self.report['districts'] if d['count_status']=='SOURCE_TABLE_AND_ARITHMETIC_VERIFIED')
        text=c.read_source(c.ROOT,self.by[key]).decode('utf-8-sig')
        self.assertIsNone(a.uncontested_statement('<nav>무투표선거구입니다.</nav>'+text))

    def test_uncontested_statement_evidence_is_exact_and_changed_layout_rejected(self):
        d=next(d for d in self.report['districts'] if d['count_status']=='SOURCE_DECLARED_UNCONTESTED')
        text=c.read_source(c.ROOT,self.by[d['count_source_target_id']]).decode('utf-8-sig')
        e=a.uncontested_statement(text)['source_cell']
        self.assertEqual(c.sha(text[e['char_start']:e['char_end']].encode()),e['span_sha256'])
        with self.assertRaises(ValueError):a.uncontested_statement(text.replace('colspan="7"','colspan="8"'))

    def test_no_identity_seniority_or_physical_polling_place_vote_promotion(self):
        self.assertEqual(self.report['member_identity_promotions'],0)
        self.assertFalse(self.report['physical_polling_place_vote_links_verified'])
        for d in self.report['districts']:
            self.assertFalse(d['ranks_calculated']);self.assertFalse(d['margins_calculated'])
            self.assertTrue(all(r['current_profile_id'] is None for r in d['candidates']))

    def test_missing_collection_is_unknown_not_zero_city_results(self):
        with tempfile.TemporaryDirectory() as td:
            r=a.build(td,write=False);self.assertEqual(r['status'],'NOT_COLLECTED')
            self.assertNotIn('polling_place_rows',r)

    def test_verified_complete_cache_reuses_all_thirty_six_sources_without_network(self):
        plan=c.initial_plan(c.ROOT)
        with tempfile.TemporaryDirectory() as td,patch.object(c,'initial_plan',return_value=plan):
            root=Path(td);self.copy_sources(root)
            def forbidden(*args,**kwargs):raise AssertionError('unexpected official request')
            r=c.collect(root,get=forbidden,post=forbidden,system=lambda:'Darwin',pause=lambda _:None)
            self.assertEqual(r['requests_this_run'],0)
            self.assertEqual(r['reused_verified_sources'],36)
            self.assertFalse(r['errors'])

    def test_tampered_cached_source_aborts_before_network_and_preserves_manifest(self):
        plan=c.initial_plan(c.ROOT)
        with tempfile.TemporaryDirectory() as td,patch.object(c,'initial_plan',return_value=plan):
            root=Path(td);self.copy_sources(root)
            out=root/c.REPORT;before=out.read_bytes()
            s=self.manifest['sources'][0];(root/s['path']).write_bytes(gzip.compress(b'tampered'))
            def forbidden(*args,**kwargs):raise AssertionError('unexpected official request')
            with self.assertRaises(ValueError):c.collect(root,get=forbidden,post=forbidden,system=lambda:'Darwin')
            self.assertEqual(out.read_bytes(),before)


if __name__=='__main__':unittest.main()
