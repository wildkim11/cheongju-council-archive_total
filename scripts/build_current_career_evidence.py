"""Reparse current-profile career lists without identity or seniority promotion."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs

from collect_current_members import _career_items, career_section
from process_meeting_segments import load_export, write_json

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def profile_url(person):
    url = person.get('official_profile_url', '')
    p = urlsplit(url)
    if (p.scheme != 'https' or p.netloc != 'council.cheongju.go.kr'
            or p.path != '/memberHome/content/profile.html' or p.fragment):
        return None
    code = person.get('official_profile_code')
    if not isinstance(code, str) or not re.fullmatch(r'[A-Za-z0-9]+', code):
        return None
    if parse_qs(p.query) != {'f_code': [code]}:
        return None
    return url


def build(root=ROOT, *, write=True):
    root = Path(root)
    manifest = json.loads((root / 'exports/analyzer/manifest.json').read_text())
    people = load_export(root, 'people', manifest)
    current = {profile_url(p): p for p in people if profile_url(p)}
    if len(current) != sum(profile_url(p) is not None for p in people):
        raise ValueError('duplicate current profile source URL')
    records, seen = [], set()
    for path in sorted((root / 'archive/source_responses/manifests').glob('*.json')):
        raw_manifest = path.read_bytes()
        document = json.loads(raw_manifest)
        for response in document.get('responses', []):
            url = response.get('url')
            if url not in current:
                continue
            if document.get('schema') != 'cheongju-source-responses/1' or path.stem != sha(raw_manifest):
                raise ValueError('career source manifest hash or schema mismatch')
            source = (root / response['path']).resolve()
            if not source.is_relative_to((root / 'archive/source_responses').resolve()):
                raise ValueError('career source path escape')
            raw = gzip.decompress(source.read_bytes())
            if sha(raw) != response['decoded_utf8_sha256'] or len(raw) != response['bytes']:
                raise ValueError('career source response hash or size mismatch')
            key = url, sha(raw)
            if key in seen:
                continue
            seen.add(key)
            html = raw.decode('utf-8')
            # Exact profile code is already tied to the current profile URL;
            # page title must also name that profile to reject wrong responses.
            person = current[url]
            title = re.search(r'<title>(.*?)</title>', html, flags=re.I | re.S)
            title_text = re.sub(r'\s+', '', title[1]) if title else ''
            if '청주시의회' + person['name'] + '의원' not in title_text:
                raise ValueError('career source profile title/name mismatch')
            section = career_section(html)
            careers = _career_items(html)
            mentions = [item for item in careers if re.search(r'\d[^\n]*대\s*(?:청주시의회|청원군의회)', item)]
            records.append({'profile_id': person['person_id'], 'name': person['name'],
                'source_url': url, 'source_manifest': str(path.relative_to(root)),
                'manifest_sha256': sha(raw_manifest), 'source_response_path': response['path'],
                'decoded_utf8_sha256': sha(raw), 'source_bytes': len(raw),
                'career_section_status': 'EXPLICIT_LIST' if section else 'HELD_NO_UNIQUE_EXPLICIT_LIST',
                'career_section_sha256': sha(section[1].encode()) if section else None,
                'careers': careers, 'numbered_council_career_mentions': mentions,
                'stored_career_items': len(person.get('career') or []),
                'stored_items_outside_reparsed_list': sum(item not in careers for item in (person.get('career') or [])),
                'career_complete': False, 'canonical_person_id': None, 'seniority': None,
                'seniority_filter_usable': False})
    represented = {r['source_url'] for r in records}
    report = {'schema': 'cheongju-current-career-evidence/1',
        'status': 'SOURCE_LISTS_REPARSED_NOT_COMPLETE_CAREERS',
        'official_site_requests': 0, 'people_input': manifest['datasets']['people'],
        'current_profiles': len(current), 'source_versions': len(records),
        'profiles_with_source': len(represented),
        'profiles_missing_source': [current[u]['person_id'] for u in sorted(set(current) - represented)],
        'profiles_with_explicit_list': len({r['profile_id'] for r in records if r['career_section_status'] == 'EXPLICIT_LIST'}),
        'career_items': sum(len(r['careers']) for r in records),
        'numbered_council_career_mentions': sum(len(r['numbered_council_career_mentions']) for r in records),
        'profiles_with_outside_items_in_stored_career': len({r['profile_id'] for r in records if r['stored_items_outside_reparsed_list']}),
        'identities_merged': 0, 'seniorities_confirmed': 0, 'rows': records,
        'interpretation': 'Career lists can omit elections, terms and losses. Numbered mentions do not establish scope, complete career, election count or cross-profile identity.'}
    if write:
        write_json(root / 'reports/current-career-evidence-latest.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    result = build(args.root)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, ensure_ascii=False, indent=2))
