import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_nec_election_samples import parse_source, build, sha

ROOT = Path(__file__).resolve().parents[1]


class NECElectionAuditTests(unittest.TestCase):
    def record(self, *, birthday='19700101', win=True, place='충청북도(청주시가선거구)', day='20260603'):
        badge = '<span class="win">당선</span>' if win else ''
        return f'<div class="result" data-birthday="{birthday}"><p class="name"><strong>시험인</strong></p><div class="list" data-election-code="6" data-election-name="{day}" data-city-code="4300" data-town-code="4302"><div class="t"><mark>[2026.06.03] 제9회 전국동시지방선거</mark> 정당 / 구·시·군의회의원선거 / {place} / 100표 {badge}</div><div>당선인 명부 링크</div></div></div>'

    def html(self, candidate='', winner=''):
        return '<html><article class="content"><ul class="tap"><li>통합</li><li>예비후보자</li><li>후보자</li><li>당선인</li></ul><div class="view"></div><div class="view"></div><div class="view">' + candidate + '</div><div class="view">' + winner + '</div></article></html>'

    def fixture(self, root, text):
        raw = text.encode(); relative = 'archive/elections/nec/source_responses/' + sha(raw) + '.txt.gz'
        source = root / relative; source.parent.mkdir(parents=True); source.write_bytes(gzip.compress(raw, mtime=0))
        report = root / 'reports/nec-election-sample-collection-latest.json'; report.parent.mkdir()
        report.write_text(json.dumps({'schema': 'cheongju-nec-election-samples/1', 'sources': [
            {'url': 'https://info.nec.go.kr/search/searchCandidate.xhtml?searchKeyword=%EC%8B%9C%ED%97%98%EC%9D%B8',
             'query_name': '시험인', 'method': 'GET', 'path': relative, 'sha256': sha(raw), 'bytes': len(raw)}]}))
        return source

    def test_candidate_and_winner_tabs_deduplicate_one_event(self):
        text = self.html(self.record(), self.record())
        events, groups = parse_source(text, '시험인')
        self.assertEqual(len(events), 1); self.assertEqual(groups, 1)
        self.assertTrue(events[0]['winner_tab_and_badge_confirmed'])
        self.assertEqual(len(events[0]['source_spans']), 2)
        for span in events[0]['source_spans']:
            self.assertEqual(sha(text[span['char_start']:span['char_end']].encode()), span['span_sha256'])

    def test_badge_or_link_in_candidate_tab_does_not_confirm_win(self):
        events, _ = parse_source(self.html(self.record(), ''), '시험인')
        self.assertFalse(events[0]['winner_tab_and_badge_confirmed'])
        self.assertFalse(events[0]['candidate_without_confirmed_win_is_loss'])
        with self.assertRaises(ValueError): parse_source(self.html('', self.record(win=False)), '시험인')

    def test_homonyms_never_merge_and_birthday_not_exported(self):
        events, groups = parse_source(self.html('', self.record() + self.record(birthday='19800202')), '시험인')
        self.assertEqual(groups, 2); self.assertEqual(len(events), 2)
        self.assertNotEqual(events[0]['nec_person_group_id'], events[1]['nec_person_group_id'])
        self.assertNotIn('19700101', json.dumps(events))
        self.assertFalse(any(e['current_person_identity_confirmed'] for e in events))

    def test_other_region_not_selected_from_name_or_navigation(self):
        events, _ = parse_source(self.html('', self.record(place='경상남도(사천시가선거구)')), '시험인')
        self.assertFalse(events[0]['target_local_council_scope'])

    def test_name_date_and_tab_shape_mismatches_rejected(self):
        for text, name in [(self.html('', self.record()), '다른사람'),
                           (self.html('', self.record(day='20180613')), '시험인'),
                           (self.html('', self.record()).replace('<li>후보자</li>', '<li>다른탭</li>'), '시험인')]:
            with self.assertRaises(ValueError): parse_source(text, name)

    def test_tampered_source_retains_previous_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = self.fixture(root, self.html('', self.record()))
            build(root); report = root / 'reports/nec-election-sample-audit-latest.json'; before = report.read_bytes()
            source.write_bytes(gzip.compress(b'tampered'))
            with self.assertRaises(ValueError): build(root)
            self.assertEqual(report.read_bytes(), before)

    def test_missing_samples_not_treated_as_zero_elections(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(build(temp)['status'], 'NOT_COLLECTED')

    def test_actual_three_samples_have_scoped_wins_but_no_person_promotion(self):
        report = build(ROOT, write=False)
        self.assertEqual(len(report['sources']), 3)
        self.assertEqual(report['target_local_council_events'], 9)
        self.assertEqual(report['target_local_council_wins'], 8)
        self.assertEqual(report['seniority_decisions'], 0)
        self.assertEqual(report['identity_merges'], 0)
