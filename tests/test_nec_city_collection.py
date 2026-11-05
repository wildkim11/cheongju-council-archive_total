import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_nec_city_election as p


class CityCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committees, cls.observed, cls.discovery = p.initial_plan(p.ROOT)

    def catalog(self):
        return {k: {'district': v, 'committee': self.committees[k[0]], 'selector_source_path': 'synthetic',
                    'selector_source_sha256': 'synthetic', 'selector_option': {}} for k,v in self.observed.items()}

    def test_actual_four_committees_and_fourteen_observed_districts_are_source_backed(self):
        self.assertEqual(len(self.committees), 4); self.assertEqual(len(self.observed), 14)
        self.assertEqual(len(self.discovery), 4)
        self.assertTrue(all(t['method']=='GET' and 'electionCode=6' in t['url'] for t in self.discovery))

    def test_thirty_two_reports_use_only_observed_codes_and_pinned_template(self):
        targets = p.report_plan(p.ROOT, self.committees, self.catalog())
        self.assertEqual(len(targets), 32)
        self.assertEqual(sum(t['menu_id']=='BIAP01' for t in targets), 4)
        for t in targets:
            values = dict(t['form_pairs'])
            self.assertEqual(values['electionId'], '0020260603')
            self.assertEqual(values['cityCode'], '4300')
            self.assertIn(values['townCode'], self.committees)
            if t['district_code']: self.assertIn((values['townCode'],values['sggTownCode']),self.observed)

    def test_exact_request_key_reuses_samples_but_never_collapses_districts(self):
        targets = p.report_plan(p.ROOT, self.committees, self.catalog())
        keys = [p.request_key(t) for t in targets]
        self.assertEqual(len(set(keys)),32)
        for target in targets:
            other=copy.deepcopy(target); other['form_pairs']=[list(x) for x in other['form_pairs']]
            self.assertEqual(p.request_key(target),p.request_key(other))

    def test_selector_provenance_keeps_option_spans_and_rejects_duplicate_values(self):
        text='<select id="townCode"><option value="1" selected>committee</option></select>'
        o=p.select_options(text,'townCode')[0]
        self.assertEqual(o['span_sha256'],p.sha(text[o['char_start']:o['char_end']].encode()))
        with self.assertRaises(ValueError):p.select_options(text.replace('</select>','<option value="1">duplicate</option></select>'),'townCode')

    def test_discovery_catalog_must_cover_all_observed_districts(self):
        sources=[]; texts={}
        for town in self.committees:
            path='synthetic-'+town; sources.append({'path':path,'sha256':'synthetic','town_code':town})
            opts=''.join('<option value="'+sgg+'">'+label+'</option>' for (t,sgg),label in self.observed.items() if t==town)
            texts[path]=('<select id="townCode"><option value="'+town+'" selected>committee</option></select><select id="sggTownCode"><option value="0">all</option>'+opts+'</select>').encode()
        with patch.object(p,'read_source',side_effect=lambda root,s:texts[s['path']]):
            catalog=p.verified_catalog(p.ROOT,self.committees,self.observed,sources)
            self.assertEqual(len(catalog),14)
            with self.assertRaises(ValueError):p.verified_catalog(p.ROOT,self.committees,self.observed,sources[:-1])
            bad=dict(self.observed);bad[next(iter(bad))]='wrong district'
            with self.assertRaises(ValueError):p.verified_catalog(p.ROOT,self.committees,bad,sources)

    def test_runtime_guard_precedes_source_or_network_calls(self):
        with patch.object(p,'initial_plan') as mocked:
            with self.assertRaises(ValueError):p.collect(system=lambda:'Linux')
            mocked.assert_not_called()


if __name__=='__main__':unittest.main()
