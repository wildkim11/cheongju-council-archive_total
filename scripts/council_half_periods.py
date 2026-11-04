"""Source-grounded council calendar halves, distinct from personal office terms.

Only curated, quoted boundary statements are admitted. Whole-term endpoints
bound each partition; no two-year formula or extension to unobserved terms.
"""
from datetime import timedelta
import hashlib
import json
from pathlib import Path

from analysis_periods import day, exact_range
from audit_stage_c import markdown_parts, canon
from process_meeting_segments import parse_label


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def verify_boundary(root, row, meetings):
    if (row.get('council_scope') != 'cheongju_integrated' or type(row.get('term')) is not int
            or row['term'] < 1 or row.get('calendar_kind') != 'council_half_calendar'
            or not isinstance(row.get('record_ref'), str) or not row['record_ref']):
        raise ValueError('invalid half boundary identity or calendar kind')
    boundary = day(row.get('boundary_date'))
    source = row['source']
    matching = [m for m in meetings if m.get('meeting_id') == source.get('meeting_id')]
    if len(matching) != 1:
        raise ValueError('missing or duplicate half-boundary source meeting')
    meeting = matching[0]
    url = 'https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=' + str(meeting['source_id'])
    if (meeting.get('term') != row['term'] or meeting.get('council_scope') != row['council_scope']
            or meeting.get('publication_status') != 'published' or meeting.get('official_url') != url
            or source.get('source_url') != url or source.get('source_path') != meeting['path']
            or source.get('sha256') != meeting['sha256']):
        raise ValueError('half boundary source metadata mismatch')
    path = (root / source['source_path']).resolve()
    if not path.is_relative_to((root / 'archive/meetings/cheongju_integrated').resolve()):
        raise ValueError('half boundary source path escape')
    raw = path.read_bytes()
    if sha(raw) != source['sha256'] or len(raw) != meeting['bytes']:
        raise ValueError('half boundary source bytes mismatch')
    text = raw.decode('utf-8')
    _, metadata, body = markdown_parts(text)
    if (metadata.get('meeting_date') != meeting['date'] or metadata.get('official_url') != url
            or metadata.get('term') != str(row['term'])
            or metadata.get('council_scope') != row['council_scope']
            or sha(canon(body).encode()) != meeting['content_sha256']):
        raise ValueError('half boundary source body or header mismatch')
    excerpts = row.get('excerpts')
    if not isinstance(excerpts, list) or not excerpts:
        raise ValueError('missing boundary excerpts')
    statements = []
    for span in excerpts:
        a, b = span.get('char_start'), span.get('char_end')
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(text):
            raise ValueError('invalid boundary excerpt coordinates')
        quote = text[a:b]
        if quote != span.get('quote') or sha(quote.encode()) != span.get('quote_sha256'):
            raise ValueError('boundary excerpt mismatch')
        start = text.rfind('\n## ○', 0, a) + 1
        end = text.find('\n', start)
        label = parse_label(text[start:end])
        next_marker = text.find('\n## ○', start)
        if (label is None or label['speaker_name'] != span.get('speaker_name')
                or label['speaker_role'] != span.get('speaker_role')
                or a < start + label['content_offset']
                or (next_marker != -1 and b > next_marker)):
            raise ValueError('boundary excerpt speaker mismatch')
        if span.get('purpose') == 'calendar_boundary':
            statements.append((quote, label))
        elif span.get('purpose') != 'personal_office_contrast':
            raise ValueError('unrecognized boundary excerpt purpose')
    if len(statements) != 1:
        raise ValueError('one calendar boundary statement required')
    quote, label = statements[0]
    mode = row.get('interpretation_rule')
    observed = day(meeting['date'])
    if mode == 'explicit_month_day_boundary_in_meeting_year':
        # Reviewed statement contains both sides of the boundary, with the year
        # supplied by the dated meeting. It is not a chair election start date.
        before = boundary - timedelta(days=1)
        if (observed.year != boundary.year or observed > boundary
                or label['speaker_role'] != '의사팀장'
                or f'전반기 임기가 {before.month}월 {before.day}일 자로 마감되는 것이 맞습니다.' not in quote
                or f'그래서 {boundary.month}월 {boundary.day}일부터 원 구성을 해서' not in quote):
            raise ValueError('explicit calendar boundary statement not reproduced')
    elif mode == 'dated_meeting_is_second_half_first_day':
        if (boundary != observed or label['speaker_role'] != '의장'
                or f'제{row["term"]}대 후반기 청주시의회가 시작되는 첫날' not in quote
                or '전반기를 마감하고' not in quote):
            raise ValueError('first-day boundary statement not reproduced')
    elif mode == 'dated_meeting_starts_new_second_half':
        if (boundary != observed or label['speaker_role'] != '시장'
                or '오늘은' not in quote
                or f'제{row["term"]}대 청주시의회가 새로운 후반기를 시작하는' not in quote
                or '날입니다.' not in quote):
            raise ValueError('new second-half boundary statement not reproduced')
    else:
        raise ValueError('unreviewed half boundary interpretation rule')
    return {'boundary_record_ref': row['record_ref'], 'boundary_record_sha256': sha(encoded(row)),
            'source_path': source['source_path'], 'source_sha256': source['sha256'],
            'source_url': url, 'meeting_date': meeting['date'], 'excerpts': excerpts,
            'interpretation_rule': mode}


def derive_halves(root, whole, boundaries=None):
    root = Path(root)
    config = root / 'config/council_half_boundaries.json'
    if boundaries is None:
        if not config.exists():
            return []
        document = json.loads(config.read_text())
        if document.get('schema') != 'cheongju-council-half-boundaries/1':
            raise ValueError('invalid half boundary schema')
        boundaries = document.get('boundaries')
    if not isinstance(boundaries, list):
        raise ValueError('invalid half boundary rows')
    if not boundaries:
        return []
    meetings = json.loads((root / 'indexes/integrated/meetings.json').read_text())
    result, seen, refs = [], set(), set()
    for row in boundaries:
        key = row.get('council_scope'), row.get('term')
        if key in seen or row.get('record_ref') in refs:
            raise ValueError('duplicate half boundary')
        seen.add(key); refs.add(row.get('record_ref'))
        parents = [p for p in whole if (p['council_scope'], p['term']) == key and p['half'] == 'whole']
        if len(parents) != 1:
            raise ValueError('missing whole-term evidence for half boundary')
        parent = parents[0]
        a, b = (day(v) for v in exact_range(parent))
        boundary = day(row.get('boundary_date'))
        if not a < boundary <= b:
            raise ValueError('half boundary outside whole term')
        evidence = verify_boundary(root, row, meetings)
        basis = {'whole_period_record_ref': parent['record_ref'],
                 'whole_period_range': [a.isoformat(), b.isoformat()], **evidence}
        for half, start, end in [('first', a, boundary - timedelta(days=1)), ('second', boundary, b)]:
            result.append({'council_scope': key[0], 'term': key[1], 'half': half,
                'start_date': start.isoformat(), 'end_date': end.isoformat(),
                'period_precision': 'exact_date', 'source_url': evidence['source_url'],
                'record_ref': row['record_ref'] + ':' + half,
                'period_kind': 'council_calendar_partition_not_personal_office_tenure',
                'source_evidence': [basis]})
    return result
