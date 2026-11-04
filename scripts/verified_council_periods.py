"""Validate whole integrated-council terms against preserved root-tree labels."""
import gzip
import hashlib
import json
from pathlib import Path
import re

from analysis_periods import exact_range

TREE_URL = 'https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsTreeGnrtn.php'
LABEL = re.compile(r'제(\d+)대 의회\((\d{4})\.\s*(\d{2})\.\s*(\d{2})\s*~\s*(\d{4})\.\s*(\d{2})\.\s*(\d{2})\s*:\s*제\d+회\s*~\s*제\d+회\)')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def node_period(node):
    m = LABEL.fullmatch(node.get('text', ''))
    if not m:
        return None
    term = int(m[1])
    if node.get('var01') != str(term) or node.get('var11') != 'SvcMntsTreeGnrtnSesn':
        raise ValueError('root tree term label/code mismatch')
    row = {'council_scope': 'cheongju_integrated', 'term': term, 'half': 'whole',
           'start_date': '-'.join(m.group(2, 3, 4)), 'end_date': '-'.join(m.group(5, 6, 7)),
           'period_precision': 'exact_date', 'source_url': TREE_URL,
           'record_ref': f'official-root-tree:cheongju_integrated:term-{term}:whole',
           'period_kind': 'officially_displayed_full_term_not_elapsed_service',
           'source_evidence': []}
    exact_range(row)
    return row


def derive(root):
    root = Path(root)
    periods = {}
    seen = set()
    for manifest in sorted((root / 'archive/source_responses/manifests').glob('*.json')):
        raw_manifest = manifest.read_bytes()
        doc = json.loads(raw_manifest)
        for response in doc.get('responses', []):
            if response.get('url') != TREE_URL:
                continue
            # Only root responses are period evidence; session trees at this
            # same POST URL have different shapes and no root labels.
            path = (root / response['path']).resolve()
            if not path.is_relative_to((root / 'archive/source_responses').resolve()):
                raise ValueError('root tree source path escape')
            raw = gzip.decompress(path.read_bytes())
            if sha(raw) != response['decoded_utf8_sha256'] or len(raw) != response['bytes']:
                raise ValueError('root tree response hash or size mismatch')
            nodes = json.loads(raw)
            if not isinstance(nodes, list):
                continue
            if not any(isinstance(n, dict) and LABEL.fullmatch(n.get('text', '')) for n in nodes):
                continue
            if doc.get('schema') != 'cheongju-source-responses/1' or manifest.stem != sha(raw_manifest):
                raise ValueError('root tree manifest hash or schema mismatch')
            if response['path'] in seen:
                continue
            seen.add(response['path'])
            local_terms = set()
            for i, node in enumerate(nodes):
                if not isinstance(node, dict):
                    raise ValueError('invalid root tree node')
                row = node_period(node)
                if row is None:
                    raise ValueError('mixed root tree labels')
                term = row['term']
                if term in local_terms:
                    raise ValueError('duplicate root tree term')
                local_terms.add(term)
                if term in periods:
                    if exact_range(periods[term]) != exact_range(row):
                        raise ValueError('conflicting official whole-term dates')
                else:
                    periods[term] = row
                periods[term]['source_evidence'].append({
                    'source_manifest': str(manifest.relative_to(root)),
                    'manifest_sha256': sha(raw_manifest), 'source_response_path': response['path'],
                    'decoded_utf8_sha256': sha(raw), 'bytes': len(raw),
                    'node_index': i, 'displayed_label': node['text']})
    return [periods[t] for t in sorted(periods)]


def load_verified(root, registry=None):
    root = Path(root)
    if registry is None:
        registry = json.loads((root / 'config/analysis_periods.json').read_text())
    if registry.get('schema') != 'cheongju-analysis-period-registry/1' or not isinstance(registry.get('periods'), list):
        raise ValueError('invalid period registry')
    if not registry['periods']:
        return []
    official = {r['record_ref']: r for r in derive(root)}
    seen = set()
    for row in registry['periods']:
        ref = row.get('record_ref')
        if not isinstance(ref, str) or ref in seen or ref not in official:
            raise ValueError('unknown or duplicate registered period')
        seen.add(ref)
        # Every registered field and provenance pointer must reproduce from
        # archived source bytes. No dates from conventions or individual terms.
        if row != official[ref]:
            raise ValueError('registered period differs from preserved root evidence')
    return registry['periods']
