import copy
import gzip
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_current_members import _career_items
from build_current_career_evidence import build, profile_url
from build_current_career_evidence import sha

ROOT = Path(__file__).resolve().parents[1]


class CurrentCareerTests(unittest.TestCase):
    def test_career_list_excludes_navigation_and_footer(self):
        html = '<nav><ul><li>다른 의원</li></ul></nav><h4>경력사항</h4><ul><li>전) 제1대 청주시의회 의원</li></ul><footer><ul><li>이용안내</li></ul></footer>'
        self.assertEqual(_career_items(html), ['전) 제1대 청주시의회 의원'])

    def test_missing_or_duplicate_heading_does_not_fallback_to_page(self):
        block = '<h4>경력사항</h4><ul><li>경력</li></ul>'
        self.assertEqual(_career_items('<ul><li>메뉴</li></ul>'), [])
        self.assertEqual(_career_items(block + block), [])
        self.assertEqual(_career_items('<h4>경력사항</h4><p>없음</p><ul><li>메뉴</li></ul>'), [])

    def test_unicode_entities_and_list_items_preserved(self):
        self.assertEqual(_career_items('<h4>경력사항</h4><ul class="depth3"><li>전) 제1대 &amp; 제3대 청주시의회 의원</li><li>현) 단체장</li></ul>'), ['전) 제1대 & 제3대 청주시의회 의원', '현) 단체장'])

    def test_nested_or_broken_list_held_without_footer_leak(self):
        self.assertEqual(_career_items('<h4>경력사항</h4><ul><li>경력<ul><li>중첩</li></ul></li></ul>'), [])
        self.assertEqual(_career_items('<h4>경력사항</h4><ul><li>경력</li></section><footer><ul><li>메뉴</li></ul>'), [])

    def fixture(self, root, title='시험인'):
        url = 'https://council.cheongju.go.kr/memberHome/content/profile.html?f_code=A1'
        people = [{'person_id': 'synthetic-A1', 'name': '시험인', 'official_profile_code': 'A1',
                   'official_profile_url': url, 'career': ['메뉴', '전) 제1대 청주시의회 의원']}]
        raw_people = (json.dumps(people[0], ensure_ascii=False) + '\n').encode()
        export = root / 'exports/analyzer'; export.mkdir(parents=True)
        (export / 'people.jsonl').write_bytes(raw_people)
        (export / 'manifest.json').write_text(json.dumps({'datasets': {'people': {'path': 'exports/analyzer/people.jsonl', 'rows': 1, 'sha256': sha(raw_people)}}}))
        raw = f'<title>청주시의회 {title}의원 누리집</title><h4>경력사항</h4><ul><li>전) 제1대 청주시의회 의원</li></ul>'.encode()
        relative = 'archive/source_responses/' + sha(raw) + '.html.gz'
        source = root / relative; source.parent.mkdir(parents=True)
        source.write_bytes(gzip.compress(raw, mtime=0))
        doc = {'schema': 'cheongju-source-responses/1', 'responses': [{'url': url, 'path': relative,
               'decoded_utf8_sha256': sha(raw), 'bytes': len(raw)}]}
        encoded = json.dumps(doc).encode()
        manifest = root / 'archive/source_responses/manifests' / (sha(encoded) + '.json')
        manifest.parent.mkdir(); manifest.write_bytes(encoded)
        return source, manifest

    def test_response_tamper_does_not_replace_previous_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source, _ = self.fixture(root)
            result = build(root)
            self.assertEqual(result['profiles_with_outside_items_in_stored_career'], 1)
            report = root / 'reports/current-career-evidence-latest.json'; before = report.read_bytes()
            source.write_bytes(gzip.compress(b'tampered'))
            with self.assertRaises(ValueError): build(root)
            self.assertEqual(report.read_bytes(), before)

    def test_manifest_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); _, manifest = self.fixture(root)
            manifest.write_bytes(manifest.read_bytes() + b' ')
            with self.assertRaises(ValueError): build(root)

    def test_wrong_profile_response_rejected_even_with_valid_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root, title='다른사람')
            with self.assertRaises(ValueError): build(root)

    def test_profile_code_namespace_and_official_url_checked(self):
        row = {'official_profile_code': 'A1', 'official_profile_url': 'https://council.cheongju.go.kr/memberHome/content/profile.html?f_code=A1'}
        self.assertIsNotNone(profile_url(row))
        for url in [row['official_profile_url'].replace('f_code=A1', 'f_code=A2'),
                    row['official_profile_url'].replace('f_code=', 'mcode='),
                    row['official_profile_url'].replace('council.cheongju.go.kr', 'example.org')]:
            self.assertIsNone(profile_url({**row, 'official_profile_url': url}))

    def test_real_current_profile_sources_are_not_complete_careers(self):
        result = build(ROOT, write=False)
        self.assertEqual(result['profiles_with_source'], 44)
        self.assertEqual(result['profiles_missing_source'], [])
        self.assertEqual(result['seniorities_confirmed'], 0)
        self.assertEqual(result['identities_merged'], 0)
        self.assertTrue(all(not r['career_complete'] and not r['seniority_filter_usable'] and r['seniority'] is None for r in result['rows']))
        self.assertTrue(all('누리집 지도' not in r['careers'] for r in result['rows']))
