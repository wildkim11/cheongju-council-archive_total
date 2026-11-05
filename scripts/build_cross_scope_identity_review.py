"""Scoped profile review across old city, old county and integrated terms.

All name buckets and profile pairs remain unapproved. No person merging,
chronological inference across numbering systems or seniority arithmetic.
"""
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path
import re
import unicodedata

from analysis_periods import SCOPES, exact_range
from build_profile_history_evidence import portrait_evidence, profile_code, preserved_rosters
from build_career_roster_crosswalk import current_rosters
from build_current_career_evidence import build as career_evidence
from process_meeting_segments import encoded, load_export, sha, write_json

ROOT=Path(__file__).resolve().parents[1]


def name_key(value):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',value or ''))


def assemble(root, people, tenures, historical=None, current=None, careers=None):
    root=Path(root); historical=historical or {}; current=current or {}; careers=careers or {'rows':[]}
    profiles={p['person_id']:(i,p) for i,p in enumerate(people,1)}
    if len(profiles)!=len(people):raise ValueError('duplicate scoped profile ID')
    by_profile=defaultdict(list)
    for i,t in enumerate(tenures,1):
        if t['person_id'] not in profiles or t.get('council_scope') not in SCOPES or type(t.get('term')) is not int or t['term']<1:
            raise ValueError('invalid cross-scope tenure/profile reference')
        by_profile[t['person_id']].append((i,t))
    buckets=defaultdict(list)
    for pid,(i,p) in profiles.items():
        normalized=name_key(p.get('name'))
        if not normalized:continue
        rows=[]
        for j,t in by_profile[pid]:
            scope,term=t['council_scope'],t['term']; back=[]
            if scope=='cheongju_integrated':
                back=[{k:v for k,v in r.items() if k!='parsed_row'} for r in historical.get((term,p.get('official_profile_url'),p['name']),[])]
                if term==4:back+=current.get((p['name'],p.get('official_profile_url')),[])
            try:
                start,end=exact_range(t); explicit={'start_date':start,'end_date':end}
            except ValueError:explicit=None
            rows.append({'council_scope':scope,'term':term,'tenure_row_ref':'tenures:'+str(j),
                'tenure_record_sha256':sha(encoded(t)),'source_url':t.get('source_url'),
                'explicit_personal_interval':explicit,'roster_response_evidence':back,
                'roster_response_reparsed':bool(back),
                'qualified_profile_code':profile_code(p,t)})
        buckets[normalized].append({'profile_id':pid,'name':p['name'],'profile_row_ref':'people:'+str(i),
            'profile_record_sha256':sha(encoded(p)),'official_profile_url':p.get('official_profile_url'),
            'source_url':p.get('source_url'),'portrait_evidence':portrait_evidence(root,p),'occurrences':rows})
    career_by=defaultdict(list)
    for r in careers['rows']:
        if r['profile_id'] not in profiles or profiles[r['profile_id']][1]['name']!=r['name']:
            raise ValueError('career source profile/name mismatch')
        if not r['numbered_council_career_mentions']:continue
        career_by[name_key(r['name'])].append({'profile_id':r['profile_id'],
            'source_url':r['source_url'],'source_response_path':r['source_response_path'],
            'decoded_utf8_sha256':r['decoded_utf8_sha256'],'career_section_sha256':r['career_section_sha256'],
            'quotes':[{'text':q,'sha256':sha(q.encode())} for q in r['numbered_council_career_mentions']]})
    groups=[]
    for normalized,members in sorted(buckets.items()):
        if len(members)<2:continue
        members.sort(key=lambda p:p['profile_id'])
        lanes=[]
        for scope in sorted(SCOPES):
            terms=sorted({o['term'] for m in members for o in m['occurrences'] if o['council_scope']==scope})
            if terms:lanes.append({'council_scope':scope,'candidate_term_numbers':terms,
                'unobserved_term_numbers_between':list(sorted(set(range(min(terms),max(terms)+1))-set(terms))),
                'missing_terms_are_losses':False,'verified_person_continuity':None})
        scopes={l['council_scope'] for l in lanes}; integrated=next((l['candidate_term_numbers'] for l in lanes if l['council_scope']=='cheongju_integrated'),[])
        pairs=[]
        for left,right in combinations(members,2):
            shared=sorted({(a['council_scope'],a['term']) for a in left['occurrences'] for b in right['occurrences'] if (a['council_scope'],a['term'])==(b['council_scope'],b['term'])})
            a,b=left['portrait_evidence'],right['portrait_evidence']
            codes_left={(o['council_scope'],*o['qualified_profile_code']) for o in left['occurrences'] if o['qualified_profile_code']}
            codes_right={(o['council_scope'],*o['qualified_profile_code']) for o in right['occurrences'] if o['qualified_profile_code']}
            pairs.append({'left_profile_id':left['profile_id'],'right_profile_id':right['profile_id'],
                'status':'REVIEW_REQUIRED','same_normalized_name':True,
                'same_verified_portrait_bytes':bool(a and b and a['sha256']==b['sha256']),
                'shared_qualified_code_keys':[list(k) for k in sorted(codes_left & codes_right)],
                'same_scope_term_multiple_profiles':[{'council_scope':s,'term':t} for s,t in shared],
                'identity_approved':False,'analysis_identity_usable':False})
        groups.append({'review_group_id':'cross-scope-name-'+sha(normalized.encode())[:24],
            'normalized_name':normalized,'status':'UNAPPROVED_NAME_REVIEW_BUCKET',
            'profiles':members,'scope_lanes':lanes,'profile_pair_candidates':pairs,
            'current_profile_career_evidence':career_by.get(normalized,[]),
            'cross_scope_review':len(scopes)>1,
            'legacy_to_integrated_review':bool('cheongju_integrated' in scopes and scopes-{'cheongju_integrated'}),
            'integrated_1_to_4_candidate_presence':all(t in integrated for t in (1,2,3,4)),
            'canonical_person_id':None,'seniority_exact':None,'verified_person_continuity':None,
            'council_number_reset_is_career_reset':False,'automatic_identity_merges':0})
    return groups


def build(root=ROOT,*,write=True):
    root=Path(root); manifest=json.loads((root/'exports/analyzer/manifest.json').read_text())
    people=load_export(root,'people',manifest);tenures=load_export(root,'tenures',manifest)
    historical,source_audit=preserved_rosters(root)
    groups=assemble(root,people,tenures,historical,current_rosters(root),career_evidence(root,write=False))
    report={'schema':'cheongju-cross-scope-identity-review/1','status':'REVIEW_BUCKETS_NOT_CANONICAL_PEOPLE',
        'official_site_requests':0,'analyzer_inputs':{k:manifest['datasets'][k] for k in ('people','tenures')},
        'profile_rows':len(people),'tenure_rows':len(tenures),'name_review_groups':len(groups),
        'cross_scope_review_groups':sum(g['cross_scope_review'] for g in groups),
        'legacy_to_integrated_review_groups':sum(g['legacy_to_integrated_review'] for g in groups),
        'integrated_1_to_4_candidate_name_groups':sum(g['integrated_1_to_4_candidate_presence'] for g in groups),
        'profile_pair_candidates':sum(len(g['profile_pair_candidates']) for g in groups),
        'scope_occurrence_counts':dict(Counter(t['council_scope'] for t in tenures)),
        'historical_roster_responses_verified':source_audit['response_count'],
        'canonical_identity_merges':0,'seniority_decisions':0,'html_identity_filter_connected':False,
        'groups':groups,
        'interpretation':'Primary-name review buckets only, including homonyms. Separate council scope/term lanes; gaps are unknown. Matching codes, portraits or term presence never approve identity or continuous tenure. Legacy roster responses require additional independent reparsing; aliases and name changes remain outside this candidate rule.'}
    if write:write_json(root/'reports/cross-scope-identity-review-latest.json',report)
    return report


if __name__=='__main__':
    r=build();print(json.dumps({k:v for k,v in r.items() if k not in {'groups','analyzer_inputs'}},ensure_ascii=False,indent=2))
