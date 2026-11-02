"""Premerger official minutes schema/identity safety contract, pre-backfill.

This module has NO network or side effects. It transforms only externally
verified legacy leaf metadata into an *unpublished staging record*.
The historical viewer flag N is NOT assumed to mean provisional, because the
verified 2014 city/county bodies do NOT show the integrated temporary notice.
Cross-council same-source numeric IDs and same names may never be merged by ID.
"""
from __future__ import annotations

import datetime as dt
import re

SCOPE_TERM_RANGES={
    "cheongju_old_city":frozenset(range(4,10)),
    "cheongwon_old_county":frozenset(range(1,7)),
}
SOURCE_PREFIXES={
    "cheongju_old_city":"/minuteschj",
    "cheongwon_old_county":"/minuteschw",
}
HOST="https://councilrec.cheongju.go.kr"
EARLIEST=dt.date(1991,4,15)
LATEST=dt.date(2014,6,30)


def normalize_verified_legacy_leaf(scope:str,term:int,session:str,
                                   committee_code:str,leaf:dict) -> dict:
    """Create an unapproved staging metadata row, never a production source."""
    if scope not in SCOPE_TERM_RANGES:
        raise ValueError("UNAUTHORIZED_LEGACY_COUNCIL_SCOPE")
    if type(term)!=int or term not in SCOPE_TERM_RANGES[scope]:
        raise ValueError("LEGACY_TERM_DOES_NOT_BELONG_TO_SCOPE")
    sid=str(leaf.get("var12") or "")
    if not re.fullmatch(r"[0-9]+",sid):
        raise ValueError("LEGACY_SOURCE_ID_NOT_OFFICIAL_NUMERIC_LEAF")
    if str(leaf.get("var01"))!=str(term):
        raise ValueError("LEGACY_LEAF_WRONG_TERM")
    if str(leaf.get("var03"))!=str(session):
        raise ValueError("LEGACY_LEAF_WRONG_SESSION")
    if str(leaf.get("var02"))!=str(committee_code):
        raise ValueError("LEGACY_LEAF_WRONG_COMMITTEE")
    raw_status=str(leaf.get("var09") or "")
    if raw_status not in ("Y","N"):
        raise ValueError("LEGACY_SOURCE_STATUS_UNKNOWN_CODE")
    official_text=str(leaf.get("text") or "")
    m=re.search(r"(?P<year>(?:19|20)\d{2})\.(?P<month>\d{2})\.(?P<day>\d{2})",official_text)
    if m is None:
        raise ValueError("LEGACY_MEETING_DATE_NOT_IN_OFFICIAL_LEAF")
    day=dt.date(int(m["year"]),int(m["month"]),int(m["day"]))
    if not EARLIEST<=day<=LATEST:
        raise ValueError("LEGACY_MEETING_DATE_OUTSIDE_PREINTEGRATION_PERIOD")
    if not str(session).isdigit() or not str(committee_code):
        raise ValueError("INVALID_OFFICIAL_SESSION_OR_COMMITTEE")
    prefix=SOURCE_PREFIXES[scope]
    url=f"{HOST}{prefix}/svc/web/cms/mnts/SvcMntsViewer.php?schSn={sid}"
    return {
        "schema":"legacy-source-staging-row/1",
        "council_scope":scope,
        "term":term,
        "session":str(session),
        "committee_code":committee_code,
        "source_id":sid,
        "meeting_id":f"{scope}:minutes-{sid}",
        "legacy_minutes_id":f"minutes-{sid}",
        "date":day.isoformat(),
        "year":day.year,
        "official_leaf_text":official_text,
        "official_url":url,
        "source_tree_publication_code":raw_status,
        "normalized_publication_status":None,
        "source_publication_semantics_verified":False,
        "eligible_for_public_analyzer":False,
        "operational_archive_write_allowed":False,
    }


def check_stage_scope_collisions(rows:list[dict]) -> dict:
    ids=[str(row["meeting_id"]) for row in rows]
    if len(ids)!=len(set(ids)):
        raise ValueError("DUPLICATE_FULL_SCOPE_AWARE_MEETING_ID")
    for row in rows:
        scope=row.get("council_scope")
        if scope not in SOURCE_PREFIXES:
            raise ValueError("INTEGRATED_OR_UNKNOWN_SOURCE_IN_LEGACY_STAGING")
        if row.get("meeting_id")!=f"{scope}:minutes-{row.get('source_id')}":
            raise ValueError("UNSAFE_CROSS_SCOPE_MEETING_ID")
        if not str(row.get("official_url","")).startswith(
                HOST+SOURCE_PREFIXES[scope]+"/svc/web/cms/mnts/"):
            raise ValueError("UNSAFE_CROSS_SCOPE_OFFICIAL_URL")
        if row.get("normalized_publication_status") is not None:
            raise ValueError("UNVERIFIED_LEGACY_FLAG_HAS_BEEN_NORMALIZED")
        if row.get("eligible_for_public_analyzer") is not False:
            raise ValueError("UNVERIFIED_LEGACY_STAGING_IMPROPER_ANALYZER_PROMOTION")
    return {
        "verified_staging_rows":len(rows),
        "distinct_scope_aware_meeting_ids":len(set(ids)),
        "individual_council_source_id_overlap_allowed":True,
        "operational_archive_write_allowed":False,
        "historical_status_semantics_unverified":True,
    }
