"""Offline, hash-checked source excerpts; date mentions are never periods."""
from __future__ import annotations

import argparse
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from collect_council_period_sources import ROOT, HOST, TARGETS

URLS = {'https://' + HOST + target for target in TARGETS}
SIGNAL = re.compile(r'제\s*\d+\s*대|전반기|후반기|임기|\d{4}\s*[.년/-]\s*\d{1,2}\s*[.월/-]\s*\d{1,2}')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            line, column = self.getpos()
            self.parts.append({'html_line': line, 'html_column': column,
                               'text': re.sub(r'\s+', ' ', data).strip()})


def excerpts(text):
    parser = Visible()
    parser.feed(text)
    result = []
    for i, part in enumerate(parser.parts):
        if SIGNAL.search(part['text']):
            result.append({**part, 'context': parser.parts[max(0, i-2):i+3],
                           'status': 'MENTION_REQUIRING_CONTEXT_REVIEW',
                           'period_usable': False})
    return result


def audit(root=ROOT, *, write=True):
    root = Path(root)
    sources = {}
    for path in sorted((root / 'archive/source_responses/manifests').glob('*.json')):
        raw_manifest = path.read_bytes()
        document = json.loads(raw_manifest)
        selected = [r for r in document.get('responses', []) if r.get('url') in URLS]
        if not selected:
            continue
        if document.get('schema') != 'cheongju-source-responses/1' or path.stem != sha(raw_manifest):
            raise ValueError('period source manifest schema or hash mismatch')
        for row in selected:
            relative = row['path']
            source = (root / relative).resolve()
            expected_root = (root / 'archive/source_responses').resolve()
            if not source.is_relative_to(expected_root):
                raise ValueError('period source response path escape')
            raw = gzip.decompress(source.read_bytes())
            digest = sha(raw)
            if digest != row['decoded_utf8_sha256'] or len(raw) != row['bytes']:
                raise ValueError('period source response hash or size mismatch')
            key = row['url'], digest
            provenance = {'path': str(path.relative_to(root)), 'sha256': sha(raw_manifest),
                          'collection_started_at': document.get('collection_started_at')}
            if key in sources:
                sources[key]['source_manifests'].append(provenance)
            else:
                sources[key] = {'source_url': row['url'], 'source_response_path': relative,
                    'decoded_utf8_sha256': digest, 'bytes': len(raw),
                    'source_manifests': [provenance],
                    'mentions': excerpts(raw.decode('utf-8'))}
    present = {url for url, _ in sources}
    result = {'schema': 'cheongju-council-period-source-audit/1',
        'status': 'SOURCES_READY_FOR_REVIEW' if present == URLS else 'MISSING_SOURCES',
        'official_site_requests': 0, 'source_versions': len(sources),
        'source_urls_captured': len(present), 'missing_source_urls': sorted(URLS - present),
        'sources': list(sources.values()), 'official_periods_promoted': 0,
        'interpretation': 'Visible mentions include navigation, historical events and personal office terms; no automatic council period inference.'}
    if write:
        output = root / 'reports/council-period-source-evidence-latest.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps({k: v for k, v in result.items() if k != 'sources'}, ensure_ascii=False, indent=2))
