"""Inclusive analysis intervals; no inferred council dates or person crosswalks.

Pure functions, no I/O. Archived explicit intervals are evidence, not human approval.
"""
from __future__ import annotations
from datetime import date
import re
from urllib.parse import urlsplit

SCOPES = {'cheongju_integrated', 'cheongju_old_city', 'cheongwon_old_county'}


def day(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('date must be YYYY-MM-DD')
    return date.fromisoformat(value)


def interval(start, end):
    a, b = day(start), day(end)
    if a > b:
        raise ValueError('reversed interval')
    return a, b


def union(ranges):
    """Canonical union, retaining real gaps and merging overlap/adjacency."""
    result = []
    for a, b in sorted(interval(*r) for r in ranges):
        if result and (a - result[-1][1]).days <= 1:
            result[-1] = (result[-1][0], max(b, result[-1][1]))
        else:
            result.append((a, b))
    return [(a.isoformat(), b.isoformat()) for a, b in result]


def intersect(left, right):
    result = []
    for a, b in union(left):
        for c, d in union(right):
            lo, hi = max(a, c), min(b, d)
            if lo <= hi:
                result.append((lo, hi))
    return union(result)


def days(ranges):
    return sum((day(b) - day(a)).days + 1 for a, b in union(ranges))


def contains(ranges, value):
    observed = day(value)
    return any(day(a) <= observed <= day(b) for a, b in union(ranges))


def official(url):
    try:
        u = urlsplit(url or '')
        return (u.scheme == 'https' and u.hostname in {
            'council.cheongju.go.kr', 'councilrec.cheongju.go.kr'
        } and not u.username and not u.password and not u.port)
    except (ValueError, TypeError):
        return False


def exact_range(row):
    if (row.get('period_precision') != 'exact_date'
            or row.get('displayed_period_conflict')
            or not official(row.get('source_url'))):
        raise ValueError('missing explicit interval evidence')
    return tuple(x.isoformat() for x in interval(row.get('start_date'), row.get('end_date')))


def _term(value):
    if type(value) is not int or value < 1:
        raise ValueError('invalid term')
    return value


def resolve(selection, registry=()):
    """Date window intersected with union of selected official term/half records.

    A missing or duplicate selected registry key holds the whole request. No July
    formula, guessed half boundary, or fallback to a larger date envelope.
    """
    if not isinstance(selection, dict) or set(selection) - {'start_date', 'end_date', 'periods'}:
        raise ValueError('invalid selection fields')
    has_dates = 'start_date' in selection or 'end_date' in selection
    window = [tuple(x.isoformat() for x in interval(selection.get('start_date'), selection.get('end_date')))] if has_dates else None
    periods = selection.get('periods', [])
    if not isinstance(periods, list) or (not periods and window is None):
        raise ValueError('empty selection')
    refs, ranges, held, seen = [], [], [], set()
    for p in periods:
        if not isinstance(p, dict) or set(p) != {'council_scope', 'term', 'half'}:
            raise ValueError('invalid period selector')
        scope, term, half = p['council_scope'], _term(p['term']), p['half']
        if scope not in SCOPES or half not in {'whole', 'first', 'second'}:
            raise ValueError('invalid scope or half')
        key = (scope, term, half)
        if key in seen:
            continue
        seen.add(key)
        matches = [r for r in registry if (r.get('council_scope'), r.get('term'), r.get('half')) == key]
        try:
            if len(matches) != 1:
                raise ValueError('missing_or_duplicate_period')
            row = matches[0]
            r = exact_range(row)
            if not isinstance(row.get('record_ref'), str) or not row['record_ref']:
                raise ValueError('missing_record_ref')
            ranges.append(r)
            refs.append({'record_ref': row['record_ref'], 'source_url': row['source_url'], **p})
        except ValueError as e:
            held.append({'selector': p, 'reason': str(e)})
    if held:
        return {'status': 'HELD', 'ranges': [], 'calendar_days': 0, 'evidence': refs, 'held': held}
    selected = union(ranges) if periods else window
    if window is not None:
        selected = intersect(selected, window)
    return {'status': 'RESOLVED' if selected else 'EMPTY', 'ranges': selected,
            'calendar_days': days(selected), 'evidence': refs, 'held': []}


def tenure_window(selection_result, rows, *, person_id, council_scope, term):
    """Intersect a single profile with recorded tenures; never merge by name.

    Unknown additional rows => PARTIAL, with no usable opportunity denominator.
    No evidence is HELD rather than a zero-day claim.
    """
    _term(term)
    if not isinstance(person_id, str) or not person_id or council_scope not in SCOPES:
        raise ValueError('missing profile identity')
    if selection_result.get('status') not in {'RESOLVED', 'EMPTY'}:
        return {'status': 'HELD', 'ranges': [], 'recorded_days': 0, 'denominator_days': None,
                'evidence': [], 'held': ['unresolved_selection']}
    candidates = [(i, r) for i, r in enumerate(rows, 1) if r.get('person_id') == person_id
                  and r.get('council_scope') == council_scope and r.get('term') == term]
    ranges, refs, held = [], [], []
    for i, row in candidates:
        try:
            r = exact_range(row)
            ranges.append(r)
            refs.append({'row_ref': 'tenures:' + str(i), 'source_url': row['source_url'], 'range': r})
        except ValueError as e:
            held.append({'row_ref': 'tenures:' + str(i), 'reason': str(e)})
    if not candidates:
        held.append({'reason': 'no_matching_tenure_records'})
    clipped = intersect(selection_result['ranges'], ranges)
    status = 'PARTIAL' if ranges and held else 'HELD' if held else 'RECORDED_INTERVALS'
    return {'status': status, 'ranges': clipped, 'recorded_days': days(clipped),
            'denominator_days': days(clipped) if status == 'RECORDED_INTERVALS' else None,
            'evidence': refs, 'held': held,
            'interpretation': 'archived_explicit_intervals_not_activity_opportunity_or_human_approval'}
