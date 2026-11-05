"""Capture and verify official preintegration roster evidence."""
import gzip
import http.client
import json
from pathlib import Path
import platform
import time
from collections import defaultdict
from urllib.parse import urlsplit

from collect_historical_members import OLD_CITY_PAGES, OLD_COUNTY_PAGES, displayed_term, parse_members
from process_meeting_segments import encoded, sha, write_json

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path('archive/source_responses')
REPORT = Path('reports/legacy-roster-source-collection-latest.json')
PAGES = {
    'cheongju_old_city': OLD_CITY_PAGES,
    'cheongwon_old_county': OLD_COUNTY_PAGES,
}
TARGETS = {url: (scope, term) for scope, pages in PAGES.items() for term, url in pages.items()}
LIMIT = 2 * 1024 * 1024


def parse_roster(url, raw):
    scope, term = TARGETS[url]
    html = raw.decode('utf-8-sig')
    if displayed_term(html) != term:
        raise ValueError(f'Unexpected displayed roster term for {url}')
    return scope, term, parse_members(html, url)


def preserved_legacy_rosters(root):
    index = defaultdict(list)
    for manifest in sorted((root / ARCHIVE / 'manifests').glob('*.json')):
        raw_manifest = manifest.read_bytes()
        document = json.loads(raw_manifest)
        if document.get('family') != 'legacy_roster_sources':
            continue
        if document.get('schema') != 'cheongju-source-responses/1' or sha(raw_manifest) != manifest.stem:
            raise ValueError('Invalid legacy roster manifest')
        for source in document['responses']:
            digest = source['decoded_utf8_sha256']
            relative = ARCHIVE / (digest + '.html.gz')
            if source['path'] != relative.as_posix() or not (root / relative).resolve().is_relative_to((root / ARCHIVE).resolve()):
                raise ValueError('Invalid legacy roster source path')
            raw = gzip.decompress((root / relative).read_bytes())
            if sha(raw) != digest or len(raw) != source['bytes']:
                raise ValueError('Legacy roster response hash or length mismatch')
            url = source['url']
            scope, term, rows = parse_roster(url, raw)
            for row in rows:
                key = scope, term, url, row['name'], row['portrait_source_url']
                index[key].append({
                    'source_manifest': manifest.relative_to(root).as_posix(),
                    'source_response_path': relative.as_posix(),
                    'decoded_utf8_sha256': digest,
                    'parsed_row_sha256': sha(encoded(row)),
                })
    return index


def capture(root=ROOT):
    if platform.system() != 'Darwin':
        raise ValueError('Official source requests require macOS')
    responses, failures = [], []
    for url in TARGETS:
        target = urlsplit(url)
        connection = http.client.HTTPSConnection(target.hostname, timeout=30)
        try:
            connection.request('GET', target.path, headers={'User-Agent': 'CheongjuCouncilArchive/0.1'})
            response = connection.getresponse()
            raw = response.read(LIMIT + 1)
            if response.status != 200 or len(raw) > LIMIT:
                raise ValueError(f'HTTP {response.status}, bytes {len(raw)}')
            parse_roster(url, raw)
            digest = sha(raw)
            relative = ARCHIVE / (digest + '.html.gz')
            path = root / relative
            if path.exists():
                if gzip.decompress(path.read_bytes()) != raw:
                    raise ValueError('Existing response hash mismatch')
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(gzip.compress(raw, mtime=0))
            responses.append({'url': url, 'path': relative.as_posix(), 'decoded_utf8_sha256': digest, 'bytes': len(raw)})
        except (OSError, ValueError, http.client.HTTPException) as exc:
            failures.append({'url': url, 'error': str(exc)[:200]})
        finally:
            connection.close()
        time.sleep(1)
    document = {'schema': 'cheongju-source-responses/1', 'family': 'legacy_roster_sources', 'responses': responses}
    manifest = ARCHIVE / 'manifests' / (sha(encoded(document)) + '.json')
    write_json(root / manifest, document)
    report = {'source_manifest': manifest.as_posix(), 'responses': len(responses), 'failures': failures}
    write_json(root / REPORT, report)
    return report


if __name__ == '__main__':
    result = capture()
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(bool(result['failures']))
