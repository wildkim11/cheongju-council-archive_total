"""Verify the bounded city snapshot, keeping unsupported result tables held."""
import json
from collections import defaultdict
from pathlib import Path

from audit_nec_report_tables import facilities, candidates, counts, table_rows, cells, evidence
from audit_nec_election_samples import visible
from collect_nec_city_election import ROOT, REPORT, initial_plan, verified_catalog, report_plan, read_source, request_key
from process_meeting_segments import write_json


def vote_summary(units, roster):
    """Summarize reconciled rows without counting ward subtotals twice."""
    total = next(row for row in units if row['row_kind'] == 'district_total')
    channels = defaultdict(list)
    for row in units:
        if row['row_kind'].endswith('_leaf'):
            channels[row['category_displayed'] or row['area_displayed']].append(row)
    return {
        'district_total_source_row': total['source_row'],
        'valid_votes': total['valid_votes'],
        'ballots': total['ballots'],
        'invalid_votes': total['invalid_votes'],
        'candidates': [
            {'ballot_label': candidate['ballot_label'], 'name': candidate['name'],
             'party_at_election': candidate['party_at_election'], 'votes': votes}
            for candidate, votes in zip(roster, total['candidate_votes'], strict=True)
        ],
        'channels': [
            {'channel': channel, 'valid_votes': sum(row['valid_votes'] for row in rows),
             'ballots': sum(row['ballots'] for row in rows),
             'candidate_votes_in_ballot_order': [sum(votes) for votes in zip(*(row['candidate_votes'] for row in rows), strict=True)],
             'source_rows': [row['source_row'] for row in rows]}
            for channel, rows in sorted(channels.items())
        ],
    }


def uncontested_statement(text):
    """Only an explicit report-body statement; navigation is not evidence."""
    table, rows = table_rows(text)
    messages = [(tr, c) for tr in rows for c in cells(tr) if c['tag']=='td' and visible(c)=='무투표선거구입니다.']
    if not messages: return None
    if (len(messages)!=1 or len(rows)!=3 or len(cells(rows[-1]))!=1
            or cells(rows[-1])[0] is not messages[0][1] or messages[0][1]['attrs'].get('colspan')!='7'
            or [visible(c) for c in cells(rows[0])] != ['읍면동명','구분','선거인수','투표수','후보자별 득표수','무효 투표수','기권자수']
            or [visible(c) for c in cells(rows[1])] != ['계']):
        raise ValueError('unexpected uncontested report statement layout')
    return {'text':'무투표선거구입니다.','source_cell':evidence(text,messages[0][1]),'table_span':evidence(text,table)}


def build(root=ROOT, *, write=True, periods_root=None):
    root = Path(root); path = root / REPORT
    if not path.exists():
        report = {'schema': 'cheongju-nec-city-election-audit/1', 'status': 'NOT_COLLECTED', 'official_site_requests': 0}
    else:
        manifest = json.loads(path.read_bytes())
        if manifest.get('schema') != 'cheongju-nec-city-election-collection/1': raise ValueError('invalid NEC city snapshot schema')
        sources = {}
        for s in manifest['sources']:
            if s['target_id'] in sources: raise ValueError('duplicate NEC city target')
            read_source(root, s)
            sources[s['target_id']] = s
        committees, observed, discovery_targets = initial_plan(root, periods_root=periods_root)
        discovery = []
        for target in discovery_targets:
            s = sources.get(target['target_id'])
            if s is None: continue
            if request_key(s) != request_key(target) or s['town_code'] != target['town_code']:
                raise ValueError('NEC city discovery request mismatch')
            discovery.append(s)
        if len(discovery) != len(discovery_targets):
            report = {'schema': 'cheongju-nec-city-election-audit/1', 'status': 'INCOMPLETE_DISCOVERY',
                      'official_site_requests': 0, 'errors': manifest.get('errors', []),
                      'unattempted_target_ids': manifest.get('unattempted_target_ids', [])}
        else:
            catalog = verified_catalog(root, committees, observed, discovery)
            targets = report_plan(root, committees, catalog)
            known = {t['target_id']: t for t in discovery_targets + targets}
            if not set(sources) <= set(known): raise ValueError('unexpected NEC city request target')
            for key, s in sources.items():
                if request_key(s) != request_key(known[key]): raise ValueError('NEC city report request mismatch')
            place_rows, facility_scopes, district_rows, held = [], [], [], []
            for town, committee in sorted(committees.items()):
                key = 'POST-BIAP01-' + town
                if key not in sources:
                    held.append({'target_id': key, 'reason': 'NOT_CAPTURED'}); continue
                s = sources[key]
                try:
                    rows, span = facilities(read_source(root,s).decode('utf-8-sig'), committee=committee)
                    if len({(r['ward_displayed'],r['polling_place_name']) for r in rows}) != len(rows):
                        raise ValueError('duplicate facility rows')
                    for row in rows: row['source_target_id'] = key
                    place_rows.extend(rows)
                    facility_scopes.append({'town_code':town,'committee':committee,'rows':len(rows),'source_target_id':key,'table_span':span})
                except ValueError as exc:
                    held.append({'target_id':key,'reason':str(exc)})
            for (town,sgg), definition in sorted(catalog.items()):
                candidate_key = 'POST-CPRI03-' + town + '-' + sgg
                count_key = 'POST-VCCP08-' + town + '-' + sgg
                row = {'town_code':town,'district_code':sgg,'district':definition['district'],
                       'committee':committees[town], 'candidate_source_target_id':candidate_key,
                       'count_source_target_id':count_key,'candidate_status':'HELD','count_status':'HELD',
                       'uncontested_status':'UNVERIFIED','candidates':None,'count_units':None,
                       'seats_verified':False,'winners_verified':False,'ranks_calculated':False,'margins_calculated':False}
                try:
                    if candidate_key not in sources: raise ValueError('candidate report NOT_CAPTURED')
                    roster, span = candidates(read_source(root,sources[candidate_key]).decode('utf-8-sig'),district=definition['district'])
                    row.update(candidate_status='SOURCE_TABLE_VERIFIED',candidates=roster,candidate_table_span=span)
                except ValueError as exc:
                    row['candidate_hold_reason']=str(exc)
                    district_rows.append(row); continue
                try:
                    if count_key not in sources: raise ValueError('count report NOT_CAPTURED')
                    text = read_source(root,sources[count_key]).decode('utf-8-sig')
                    statement = uncontested_statement(text)
                    if statement:
                        row.update(count_status='SOURCE_DECLARED_UNCONTESTED',uncontested_status='OFFICIAL_COUNT_REPORT_STATEMENT',
                                   uncontested_evidence=statement,count_metrics_status='NOT_APPLICABLE_UNCONTESTED')
                    else:
                        units, checks, span = counts(text,roster)
                        row.update(count_status='SOURCE_TABLE_AND_ARITHMETIC_VERIFIED',count_units=units,checks=checks,
                                   count_table_span=span,vote_summary=vote_summary(units,roster))
                except ValueError as exc:
                    row['count_hold_reason']=str(exc)
                district_rows.append(row)
            complete_capture = set(sources) == set(known) and not manifest.get('errors') and not manifest.get('unattempted_target_ids')
            accounted = all(r['count_status']!='HELD' and r['candidate_status']=='SOURCE_TABLE_VERIFIED' for r in district_rows)
            report = {'schema':'cheongju-nec-city-election-audit/1',
                'status':'CITY_TABLES_AND_UNCONTESTED_STATEMENTS_VERIFIED' if accounted and not held and complete_capture else 'PARTIAL_CITY_TABLES_WITH_HELD_RESULTS',
                'official_site_requests':0,'election_id':'0020260603','collection_complete':complete_capture,
                'committee_catalog_count':len(committees),'district_catalog_count':len(catalog),
                'facility_committees_verified':len(facility_scopes),'polling_place_rows':len(place_rows),
                'candidate_districts_verified':sum(r['candidate_status']=='SOURCE_TABLE_VERIFIED' for r in district_rows),
                'candidate_rows':sum(len(r['candidates'] or []) for r in district_rows),
                'count_districts_verified':sum(r['count_status']=='SOURCE_TABLE_AND_ARITHMETIC_VERIFIED' for r in district_rows),
                'officially_uncontested_districts':sum(r['count_status']=='SOURCE_DECLARED_UNCONTESTED' for r in district_rows),
                'count_districts_held':sum(r['count_status']=='HELD' for r in district_rows),
                'count_unit_rows':sum(len(r['count_units'] or []) for r in district_rows),
                'facility_scopes':facility_scopes,'facilities':place_rows,'districts':district_rows,'held_facilities':held,
                'sources':{k:{f:s[f] for f in ('path','sha256','bytes','method','url','captured_at')} for k,s in sources.items()},
                'whole_city_facility_tables_verified':len(facility_scopes)==len(committees) and not held,
                'all_district_count_reports_accounted':all(r['count_status']!='HELD' for r in district_rows),
                'whole_city_election_results_verified':False,'member_identity_promotions':0,
                'physical_polling_place_vote_links_verified':False,'html_connected':False}
    if write: write_json(root / 'reports/nec-city-election-audit-latest.json',report)
    return report


if __name__=='__main__':
    r=build(); print(json.dumps({k:v for k,v in r.items() if k not in {'facility_scopes','facilities','districts','sources','held_facilities'}},ensure_ascii=False,indent=2))
