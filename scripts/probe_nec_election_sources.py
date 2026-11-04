"""Bounded public NEC search transport inspection, macOS only, no submissions."""
import gzip
import hashlib
import http.client
import json
from pathlib import Path
import platform
import re
import ssl
import time
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://info.nec.go.kr/search/searchCandidate.xhtml'
LIMIT = 2 * 1024 * 1024


def fetch(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'info.nec.go.kr' or parsed.fragment:
        raise ValueError('unexpected NEC source URL')
    conn = http.client.HTTPSConnection(parsed.hostname, timeout=25, context=ssl.create_default_context())
    try:
        conn.request('GET', parsed.path + ('?' + parsed.query if parsed.query else ''),
                     headers={'User-Agent': 'CheongjuCouncilArchive-SourceInspection/0.1'})
        response = conn.getresponse()
        raw = response.read(LIMIT + 1)
        if response.status != 200 or len(raw) > LIMIT:
            raise ValueError(f'NEC source HTTP {response.status}, bytes {len(raw)}')
        return raw
    finally:
        conn.close()


def inspect(root=ROOT, *, request=fetch, system=platform.system):
    if system() != 'Darwin':
        raise ValueError('official source transport requires macOS')
    root = Path(root)
    sources, errors = [], []
    queue = [URL]
    for index in range(3):
        if index >= len(queue):
            break
        url = queue[index]
        try:
            raw = request(url)
            text = raw.decode('utf-8-sig')
            digest = hashlib.sha256(raw).hexdigest()
            relative = 'archive/elections/nec/source_responses/' + digest + '.txt.gz'
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and gzip.decompress(path.read_bytes()) != raw:
                raise ValueError('NEC content-addressed response mismatch')
            if not path.exists():
                path.write_bytes(gzip.compress(raw, mtime=0))
            sources.append({'url': url, 'method': 'GET', 'path': relative,
                            'sha256': digest, 'bytes': len(raw)})
            if index == 0:
                scripts = re.findall(r'<script\b[^>]*src=["\']([^"\']+)', text, flags=re.I)
                for href in scripts:
                    target = urljoin(URL, href)
                    parsed = urlsplit(target)
                    if (parsed.scheme == 'https' and parsed.netloc == 'info.nec.go.kr'
                            and parsed.path.endswith('.js')
                            and re.search('search|candidate', parsed.path, flags=re.I)
                            and target not in queue):
                        queue.append(target)
                queue = queue[:3]
            if index + 1 < len(queue):
                time.sleep(1)
        except Exception as exc:
            errors.append({'url': url, 'error': type(exc).__name__ + ': ' + str(exc)[:200]})
            break
    report = {'schema': 'cheongju-nec-source-inspection/1',
        'status': 'SOURCE_CAPTURED_FOR_TRANSPORT_REVIEW' if sources and not errors else 'INCOMPLETE',
        'maximum_requests': 3, 'attempts_per_request': 1, 'runtime_platform': system(),
        'sources': sources, 'errors': errors, 'election_rows_collected': 0,
        'seniority_decisions': 0, 'note': 'Public search HTML and observed search JS only. No form submission, identity merge or election-result inference.'}
    output = root / 'reports/nec-source-inspection-latest.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    result = inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'SOURCE_CAPTURED_FOR_TRANSPORT_REVIEW' else 1)
