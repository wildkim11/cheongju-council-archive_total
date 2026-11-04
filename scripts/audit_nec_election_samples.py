"""Offline election facts from bounded NEC public name-search samples.

Homonym groups remain separate. Only the winner tab plus its explicit winner
badge confirms a displayed win. No name-only current-person link or seniority.
"""
import argparse
from collections import Counter
from datetime import date
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, parse_qs

from process_meeting_segments import write_json

ROOT = Path(__file__).resolve().parents[1]


def sha(raw): return hashlib.sha256(raw).hexdigest()
def classes(node): return set(node['attrs'].get('class', '').split())
def visible(node): return re.sub(r'\s+', ' ', ''.join(c if isinstance(c, str) else visible(c) + ' ' for c in node['children'])).strip()
def find(node, predicate):
    for child in node['children']:
        if isinstance(child, dict):
            if predicate(child): yield child
            yield from find(child, predicate)


class DOM(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.offsets = [0]
        for m in re.finditer('\n', text): self.offsets.append(m.end())
        self.root = {'tag': 'root', 'attrs': {}, 'children': [], 'start': 0, 'end': len(text)}
        self.stack = [self.root]
        self.feed(text)

    def position(self):
        line, column = self.getpos(); return self.offsets[line-1] + column

    def handle_starttag(self, tag, attrs):
        node = {'tag': tag, 'attrs': dict(attrs), 'children': [], 'start': self.position(), 'end': None}
        self.stack[-1]['children'].append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)
        else: node['end'] = node['start'] + len(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        before = len(self.stack); self.handle_starttag(tag, attrs)
        if len(self.stack) > before: self.stack.pop()['end'] = self.position() + len(self.get_starttag_text())

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i]['tag'] == tag:
                for node in self.stack[i:]: node['end'] = self.position() + len(tag) + 3
                del self.stack[i:]; return

    def handle_data(self, data): self.stack[-1]['children'].append(data)


def parse_source(text, query_name):
    dom = DOM(text)
    articles = list(find(dom.root, lambda n: n['tag'] == 'article' and 'content' in classes(n)))
    if len(articles) != 1: raise ValueError('NEC result article missing or duplicated')
    article = articles[0]
    tabs = list(find(article, lambda n: n['tag'] == 'ul' and 'tap' in classes(n)))
    if len(tabs) != 1: raise ValueError('NEC result tabs missing or duplicated')
    labels = [visible(n) for n in tabs[0]['children'] if isinstance(n, dict) and n['tag'] == 'li']
    views = [n for n in article['children'] if isinstance(n, dict) and n['tag'] == 'div' and 'view' in classes(n)]
    if labels != ['통합', '예비후보자', '후보자', '당선인'] or len(views) != 4:
        raise ValueError('NEC result tab order changed')
    events, homonyms = {}, set()
    for label in ('후보자', '당선인'):
        view = views[labels.index(label)]
        for result in find(view, lambda n: n['tag'] == 'div' and 'result' in classes(n)):
            names = list(find(result, lambda n: n['tag'] == 'p' and 'name' in classes(n)))
            strong = list(find(names[0], lambda n: n['tag'] == 'strong')) if len(names) == 1 else []
            if len(strong) != 1 or visible(strong[0]) != query_name:
                raise ValueError('NEC returned name differs from query')
            birthday = result['attrs'].get('data-birthday', '')
            if not re.fullmatch(r'\d{8}', birthday): raise ValueError('NEC homonym group missing birth-date key')
            group = 'nec-person-group-' + sha((query_name + ':' + birthday).encode())[:24]
            homonyms.add(group)
            for node in [n for n in result['children'] if isinstance(n, dict) and n['tag'] == 'div' and 'list' in classes(n)]:
                headings = [n for n in node['children'] if isinstance(n, dict) and n['tag'] == 'div' and 't' in classes(n)]
                if len(headings) != 1 or node['end'] is None: raise ValueError('NEC election list boundary missing')
                heading = visible(headings[0]); attrs = node['attrs']
                marks = list(find(headings[0], lambda n: n['tag'] == 'mark'))
                displayed = re.search(r'\[(\d{4})\.(\d{2})\.(\d{2})\]', visible(marks[0])) if len(marks) == 1 else None
                raw_day = attrs.get('data-election-name', '')
                if not displayed or raw_day != ''.join(displayed.groups()):
                    raise ValueError('NEC election displayed date/data mismatch')
                election_day = date(int(displayed[1]), int(displayed[2]), int(displayed[3])).isoformat()
                win = any(visible(n) == '당선' for n in find(headings[0], lambda n: n['tag'] == 'span' and 'win' in classes(n)))
                if label == '당선인' and not win: raise ValueError('NEC winner tab row lacks explicit winner badge')
                codes = {k: attrs.get('data-' + k, '') for k in ('election-type', 'old-election-type', 'election-code', 'election-name', 'city-code', 'sgg-city-code', 'town-code', 'sgg-town-code', 'date-code', 'time-code')}
                if any(not re.fullmatch(r'\d+', codes[k]) for k in ('election-code', 'city-code', 'town-code')):
                    raise ValueError('NEC election codes missing')
                key = sha(json.dumps([group, election_day, codes], sort_keys=True).encode())
                municipal_council = '구·시·군의회의원선거' in heading or '기초의원비례대표선거' in heading
                location = re.search(r'충청북도\s*\(\s*(청주시|청원군)[^)]*\)', heading)
                selected = municipal_council and bool(location)
                row = events.setdefault(key, {'event_id': 'nec-event-' + key[:24],
                    'nec_person_group_id': group, 'query_name': query_name, 'election_date': election_day,
                    'displayed_heading': heading, 'codes': codes, 'tabs': [], 'source_spans': [],
                    'winner_tab_and_badge_confirmed': False, 'candidate_without_confirmed_win_is_loss': False,
                    'target_local_council_scope': bool(selected),
                    'displayed_municipality': location[1] if selected else None,
                    'current_person_identity_confirmed': False, 'seniority_usable': False})
                if row['displayed_heading'] != heading: raise ValueError('NEC duplicate event display conflict')
                if label not in row['tabs']: row['tabs'].append(label)
                row['winner_tab_and_badge_confirmed'] |= label == '당선인' and win
                raw_span = text[node['start']:node['end']]
                row['source_spans'].append({'tab': label, 'char_start': node['start'], 'char_end': node['end'],
                                             'span_sha256': sha(raw_span.encode())})
    return list(events.values()), len(homonyms)


def build(root=ROOT, *, write=True):
    root = Path(root)
    collection_path = root / 'reports/nec-election-sample-collection-latest.json'
    if not collection_path.exists():
        report = {'schema': 'cheongju-nec-election-sample-audit/1', 'status': 'NOT_COLLECTED',
                  'official_site_requests': 0, 'seniority_decisions': 0, 'sources': [], 'events': []}
    else:
        raw_collection = collection_path.read_bytes(); collection = json.loads(raw_collection)
        if collection.get('schema') != 'cheongju-nec-election-samples/1': raise ValueError('invalid NEC sample collection schema')
        events, sources = [], []
        seen = set()
        for source in collection['sources']:
            u = urlsplit(source['url'])
            if (u.scheme != 'https' or u.netloc != 'info.nec.go.kr' or u.path != '/search/searchCandidate.xhtml'
                    or parse_qs(u.query) != {'searchKeyword': [source['query_name']]} or source['method'] != 'GET'):
                raise ValueError('NEC query provenance mismatch')
            if source['query_name'] in seen: raise ValueError('duplicate NEC sample name')
            seen.add(source['query_name'])
            path = (root / source['path']).resolve()
            if not path.is_relative_to((root / 'archive/elections/nec/source_responses').resolve()): raise ValueError('NEC sample path escape')
            raw = gzip.decompress(path.read_bytes())
            if sha(raw) != source['sha256'] or len(raw) != source['bytes']: raise ValueError('NEC sample source hash/size mismatch')
            rows, homonyms = parse_source(raw.decode('utf-8-sig'), source['query_name'])
            for row in rows:
                row['source_response_path'] = source['path']; row['source_response_sha256'] = source['sha256']; row['source_url'] = source['url']
            events.extend(rows)
            sources.append({**source, 'name_groups': homonyms, 'unique_candidate_or_winner_events': len(rows),
                'target_local_council_events': sum(r['target_local_council_scope'] for r in rows),
                'target_local_council_wins': sum(r['target_local_council_scope'] and r['winner_tab_and_badge_confirmed'] for r in rows)})
        selected = [r for r in events if r['target_local_council_scope']]
        report = {'schema': 'cheongju-nec-election-sample-audit/1', 'status': 'SOURCE_FACTS_NOT_CURRENT_PERSON_IDENTITY',
            'official_site_requests': 0, 'collection_manifest_sha256': sha(raw_collection), 'sources': sources,
            'collection_complete': collection.get('status') == 'SAMPLES_CAPTURED_FOR_OFFLINE_REVIEW' and len(sources) == 3 and not collection.get('errors'),
            'target_profiles_are_query_targets_only': True,
            'unique_candidate_or_winner_events': len(events), 'target_local_council_events': len(selected),
            'target_local_council_wins': sum(r['winner_tab_and_badge_confirmed'] for r in selected),
            'identity_merges': 0, 'seniority_decisions': 0, 'events': events,
            'interpretation': 'Only published winner-tab + explicit badge rows are displayed wins. Name groups separated by hashed source birth-date key. No current-person links, complete-history or loss inference. Full source bytes retained for review.'}
    if write: write_json(root / 'reports/nec-election-sample-audit-latest.json', report)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, default=ROOT)
    args = p.parse_args(); r = build(args.root)
    print(json.dumps({k: v for k, v in r.items() if k not in ('events',)}, ensure_ascii=False, indent=2))
