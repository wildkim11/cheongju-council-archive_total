"""Offline, evidence-preserving speech segmentation and shared activity-role ledger.

No official-site calls, no inferred questions/answers, no name-only identity
promotion. Source Markdown and source-only analyzer exports remain unchanged.
"""
from __future__ import annotations
import argparse,bisect,collections,datetime as dt,gzip,hashlib,io,json,re
from pathlib import Path
from audit_stage_c import markdown_parts,canon
ROOT=Path(__file__).resolve().parents[1]
VERSION='meeting-segments/1'
MARKER=re.compile(r'(?m)^(?:## )?○[^\n]*')
WIDE=re.compile(r'[\u2000-\u200a\u202f\u205f\u3000]|[ \t]{2,}')
NAME=r'[가-힣]{2,5}'
COUNCIL={'의원','위원','의장','부의장','위원장','의장직무대행','의장직무대리','위원장직무대행','위원장직무대리','위원장대리','위원장대행'}
EXTERNAL={'증인','참고인','진술인','공술인'}
ROLE_ENDINGS=tuple(sorted(COUNCIL|EXTERNAL|{'과장','팀장','국장','구청장','부시장','시장','소장','관장','본부장','센터장','담당관','전문위원','사무국장','사무처장','이사장','대표','대표이사','단장','실장','의사담당','주무관','사무관','주사','담당','부장','차장','원장','주임','상임이사','이사','공보관','대변인','사무총장','총장','감사관','기획관','보좌관','회장','동장','면장','읍장','대표이사후보자'},key=lambda x:(-len(x),x)))
SECTION=re.compile(r'^(?:출석|참석|청가|기록\s*담당|기타\s*참석|첨부|붙임|의사일정|부의된|의결|서명|청주시의회\s*회의록)')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def encoded(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def write_json(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(encoded(value))
def pack(raw):
 buffer=io.BytesIO()
 with gzip.GzipFile(filename='',mode='wb',compresslevel=6,fileobj=buffer,mtime=0) as stream:stream.write(raw)
 return buffer.getvalue()
def date(value):
 try:return dt.date.fromisoformat(value) if value else None
 except (ValueError,TypeError):return None

def recognized_role(role):
 plain=re.sub(r'\([^)]*\)','',role).replace(' ','')
 return plain.endswith(ROLE_ENDINGS)

def document_heading(header):
 """Recognize documentary markers before attempting a person-name fallback."""
 rest=re.sub(r'^(?:## )?○\s*','',header).strip()
 return bool(SECTION.match(rest) or (not WIDE.search(rest) and (re.search(r'끝에\s*실음|의\s*건(?:은|$)',rest) or (re.match(r'^(?:## )?○[ \t]+',header) and re.search(r'(?:조례(?:안|\s*(?:일부|전부)개정조례안)|동의안|결의안|건의안)\s*$',rest)))))

def parse_label(header):
 """Return explicit label fields and content offset within the header only."""
 prefix=re.match(r'^(?:## )?○',header)
 if not prefix:return None
 offset=prefix.end();rest=header[offset:];trim=len(rest)-len(rest.lstrip());offset+=trim;rest=rest.lstrip()
 if document_heading(header):return None
 delimiter=WIDE.search(rest)
 label=rest[:delimiter.start()].strip() if delimiter else rest.strip()
 candidates=[]
 for pattern in (rf'^(?P<role>.+?)\s+(?P<name>{NAME})$',rf'^(?P<name>{NAME})\s+(?P<role>.+?)$',rf'^(?P<role>[^()]+)\((?P<name>{NAME})\)$'):
  m=re.match(pattern,label)
  if m and recognized_role(m['role']):candidates.append((m['name'],m['role'],len(label)))
 if not candidates and not delimiter:
  roles='|'.join(re.escape(x) for x in ROLE_ENDINGS)
  for pattern in (rf'^(?P<name>{NAME})\s+(?P<role>(?:{roles}))(?=\s|$)',rf'^(?P<role>[가-힣A-Za-z0-9·ㆍ()]*?(?:{roles}))\s+(?P<name>{NAME})(?=\s|$)'):
   m=re.match(pattern,rest)
   if m:candidates.append((m['name'],m['role'],m.end()))
 if not candidates:return None
 unique={(n,r) for n,r,_ in candidates}
 if len(unique)!=1:return None
 name,role,end=candidates[0];content=offset+(delimiter.end() if delimiter else end)
 while content<len(header) and header[content].isspace():content+=1
 normalized=role.replace(' ','')
 category='council_presiding' if normalized in COUNCIL and ('의장' in normalized or '위원장' in normalized) else 'council_member' if normalized in COUNCIL else 'external' if normalized in EXTERNAL else 'executive_or_staff'
 return {'speaker_name':name,'speaker_role':role,'speaker_category':category,'content_offset':content,'label':rest[:end]}

class Identities:
 def __init__(self,people,tenures):
  self.people={p['person_id']:p for p in people}
  if len(self.people)!=len(people):raise ValueError('duplicate person IDs')
  self.by_name=collections.defaultdict(list);fingerprint=[]
  for t in tenures:
   p=self.people.get(t['person_id'])
   if not p:raise ValueError('tenure references absent person')
   self.by_name[(t['council_scope'],p['name'])].append(t)
   fingerprint.append((t['person_id'],p['name'],t['council_scope'],t['term'],t.get('start_date'),t.get('end_date'),t.get('source_url')))
  self.fingerprint=sha(encoded(sorted(fingerprint,key=lambda x:tuple(str(y) for y in x))))
 def resolve(self,name,scope,when,term=None,council=True,meeting_context=None):
  if not council:return {'person_id':None,'candidate_person_ids':[],'identity_status':'not_a_council_speaker'}
  rows=[t for t in self.by_name.get((scope,name),[]) if term is None or t['term']==term]
  when=date(when);dated=[]
  for t in rows:
   start,end=date(t.get('start_date')),date(t.get('end_date'))
   if when and start and end and start<=when<=end:dated.append(t)
  ids=sorted({t['person_id'] for t in dated})
  undated_same_term=bool(dated and any(t['person_id']!=ids[0] and t['term']==dated[0]['term'] and (not date(t.get('start_date')) or not date(t.get('end_date'))) for t in rows)) if len(ids)==1 else False
  if len(ids)==1 and not undated_same_term:return {'person_id':ids[0],'candidate_person_ids':[],'identity_status':'resolved_explicit_tenure','tenure_interval_verified':True,'resolved_term':dated[0]['term'],'identity_evidence_ref':'tenures:'+ids[0]}
  candidates=sorted({t['person_id'] for t in rows})
  outside=lambda t:bool(when and ((date(t.get('start_date')) and when<date(t['start_date'])) or (date(t.get('end_date')) and when>date(t['end_date']))))
  if meeting_context and when and term is not None and len(candidates)==1 and rows and not any(outside(t) for t in rows):
   valid_context=(meeting_context.get('term')==term and meeting_context.get('council_scope')==scope and meeting_context.get('date')==when.isoformat() and re.match(r'^https://councilrec\.cheongju\.go\.kr/',meeting_context.get('official_url','')) and re.fullmatch(r'[0-9a-f]{64}',meeting_context.get('sha256','')))
   official_roster=any(re.match(r'^https://council\.cheongju\.go\.kr/',t.get('source_url','')) for t in rows)
   if valid_context and official_roster:
    return {'person_id':candidates[0],'candidate_person_ids':[],'identity_status':'resolved_source_meeting_term','resolved_term':term,'tenure_interval_verified':False,'identity_evidence_ref':'tenures:'+candidates[0]+';meeting:'+meeting_context['meeting_id']}
  return {'person_id':None,'candidate_person_ids':sorted({t['person_id'] for t in rows}),'identity_status':'ambiguous_dated_tenure' if len(ids)>1 or undated_same_term else 'invalid_or_missing_date' if not when else 'outside_known_tenure' if rows and all(outside(t) for t in rows) else 'candidate_missing_dated_tenure' if rows and any(not date(t.get('start_date')) or not date(t.get('end_date')) for t in rows) else 'outside_known_tenure' if rows else 'unmatched_person'}

def paragraphs(text,start,end,line_starts,segment_id):
 out=[];cursor=start
 for sep in list(re.finditer(r'\n[ \t]*\n',text[start:end]))+[None]:
  stop=start+sep.start() if sep else end;block=text[cursor:stop];a=cursor+len(block)-len(block.lstrip());b=stop-(len(block)-len(block.rstrip()))
  if a<b:out.append({'paragraph_id':segment_id+':p'+str(len(out)+1),'char_start':a,'char_end':b,'line_start':bisect.bisect_right(line_starts,a),'line_end':bisect.bisect_right(line_starts,b-1),'text_sha256':sha(text[a:b].encode())})
  cursor=start+sep.end() if sep else end
 return out

def segment_document(text,row,identities):
 _,_,body=markdown_parts(text)
 if sha(canon(body).encode())!=row['content_sha256']:raise ValueError('meeting content hash mismatch: '+row['meeting_id'])
 pieces=text.split('\n\n',2);start=len(pieces[0])+2+len(pieces[1])+2
 markers=list(MARKER.finditer(text,start));starts=([start] if not markers or markers[0].start()>start else [])+[m.start() for m in markers]
 ends=starts[1:]+[len(text)];line_starts=[0]+[m.end() for m in re.finditer('\n',text)];out=[]
 for n,(a,b) in enumerate(zip(starts,ends),1):
  if a==b:continue
  line=text[a:text.find('\n',a) if '\n' in text[a:b] else b];label=parse_label(line);sid=row['meeting_id']+'@'+row['sha256'][:12]+':s'+str(n)
  rec={'segment_id':sid,'kind':'speech' if label else 'document_section' if MARKER.match(text,a) and document_heading(line) else 'unparsed_marker' if MARKER.match(text,a) else 'preamble','char_start':a,'char_end':b,'line_start':bisect.bisect_right(line_starts,a),'line_end':bisect.bisect_right(line_starts,b-1)}
  content_start=a
  if label:
   content_start=a+label['content_offset'];rec.update({k:v for k,v in label.items() if k!='content_offset'})
   rec.update(identities.resolve(label['speaker_name'],row['council_scope'],row['date'],row['term'],label['speaker_category'].startswith('council_'),meeting_context=row))
   rec['speech_function']='unclassified'
  rec['content_start']=content_start;rec['paragraphs']=paragraphs(text,content_start,b,line_starts,sid);out.append(rec)
 if out and (out[0]['char_start']!=start or out[-1]['char_end']!=len(text) or any(x['char_end']!=y['char_start'] for x,y in zip(out,out[1:]))):raise ValueError('source-range coverage failure')
 return out

def load_export(root,name,manifest):
 meta=manifest['datasets'][name];p=root/'exports/analyzer'/f'{name}.jsonl';raw=p.read_bytes()
 if sha(raw)!=meta['sha256']:raise ValueError('input export hash mismatch: '+name)
 rows=[json.loads(line) for line in raw.splitlines()]
 if len(rows)!=meta['rows']:raise ValueError('input row mismatch: '+name)
 return rows

def activity_roles(data,identities,body_evidence=None):
 body_evidence=body_evidence or {}
 result=[];seen=set();bills={(b['council_scope'],b['term'],str(b['internal_number'])):b for b in data['bills']}
 def add(rec):
  if rec['activity_id'] in seen:raise ValueError('duplicate activity role ID')
  seen.add(rec['activity_id']);result.append(rec)
 for dataset,kind in [('five_minute_speeches','five_minute_speech'),('city_questions','city_question'),('written_questions','written_question')]:
  for line,r in enumerate(data[dataset],1):
   identity=identities.resolve(r.get('speaker_name'),r['council_scope'],r.get('date'))
   exact=body_evidence.get(dataset+':'+str(r['source_id']),[])
   if len(exact)==1:
    proof=exact[0]
    if identity.get('person_id') and identity['person_id']!=proof['person_id']:
     identity={'person_id':None,'candidate_person_ids':sorted({identity['person_id'],proof['person_id']}),'identity_status':'identity_evidence_conflict'}
    else:
     if not identity.get('person_id'):identity.update(person_id=proof['person_id'],candidate_person_ids=[],identity_status='resolved_cross_source_exact_body',resolved_term=proof['term'],tenure_interval_verified=False)
     identity['source_link']=proof
   add({'activity_id':dataset+':'+str(r['source_id'])+':speaker','kind':kind,'role':'speaker','date':r.get('date'),'term':identity.get('resolved_term'),'person_name':r.get('speaker_name'),'title':r.get('title') or r.get('title_list'),'official_url':r.get('official_url') or r.get('detail_url'),'source_dataset':dataset,'source_row_1based':line,**identity})
 for line,r in enumerate(data['bill_proposers_member_only'],1):
  b=bills.get((r['council_scope'],r['term'],str(r['internal_number'])))
  if not b or r['proposer_role'] not in ('representative','co_proposer'):raise ValueError('invalid safe proposer reference')
  institutional=any(v and v!='의원' for v in [b.get('proposer_type_list'),b.get('proposer_type')])
  if not any(b.get(k)=='의원' for k in ('proposer_type_list','proposer_type')):raise ValueError('bill is not explicitly member-proposed')
  if institutional:raise ValueError('institutional proposer mixed into activity roles')
  pid=r.get('person_id');p=identities.people.get(pid)
  valid_ids={t['person_id'] for t in identities.by_name.get((r['council_scope'],r['person_name']),[]) if t['term']==r['term']}
  if pid and (not p or p['name']!=r['person_name'] or pid not in valid_ids or r.get('resolution_status')!='resolved_exact_term'):raise ValueError('invalid archived proposer identity')
  add({'activity_id':'bill:'+str(r['term'])+':'+str(r['internal_number'])+':'+str(pid or r['person_name'])+':'+r['proposer_role'],'kind':'bill','role':r['proposer_role'],'date':b.get('proposal_date'),'term':r['term'],'person_name':r['person_name'],'title':b['title'],'official_url':r['source_url'],'source_dataset':'bill_proposers_member_only','source_row_1based':line,'person_id':pid,'candidate_person_ids':r.get('candidate_person_ids',[]),'identity_status':'archive_exact_term_link' if pid else 'unmatched_person','temporal_verification':'term_only_not_exact_dates'})
 return result

def process(root=ROOT):
 processor_sha=sha(Path(__file__).read_bytes())
 root=Path(root);out=root/'exports/processing';out.mkdir(parents=True,exist_ok=True);mf=json.loads((root/'exports/analyzer/manifest.json').read_text());names=['people','tenures','bills','bill_proposers_member_only','five_minute_speeches','city_questions','written_questions'];data={n:load_export(root,n,mf) for n in names};identities=Identities(data['people'],data['tenures'])
 targets=collections.defaultdict(list)
 for dataset in ('five_minute_speeches','city_questions'):
  for a in data[dataset]:
   needle=canon(a.get('body_text') or '')
   if len(needle)>=80:targets[(a.get('date'),a.get('speaker_name'))].append((dataset+':'+str(a['source_id']),needle))
 target_dates={k[0] for k in targets};body_evidence=collections.defaultdict(list)
 rows=json.loads((root/'indexes/integrated/meetings.json').read_text());seen=set();old=json.loads((out/'meeting_segments_catalog.json').read_text()) if (out/'meeting_segments_catalog.json').exists() else [];cache={r['meeting_id']:r for r in old};catalog=[];counts=collections.Counter();kinds=collections.Counter();links=collections.Counter();parsed_roles=collections.Counter();reused=0;rebuilt=0
 for row in sorted(rows,key=lambda r:r['meeting_id']):
  mid=row['meeting_id']
  if mid in seen:raise ValueError('duplicate meeting ID')
  seen.add(mid);rel=Path(row['path'])
  if rel.is_absolute() or '..' in rel.parts or rel.parts[:2]!=('archive','meetings'):raise ValueError('unsafe source path')
  raw=(root/rel).read_bytes()
  if sha(raw)!=row['sha256']:raise ValueError('meeting original hash mismatch: '+mid)
  segs=None
  signature=sha(encoded([VERSION,processor_sha,mid,row['sha256'],identities.fingerprint]));target='segments/'+signature+'.json.gz';prior=cache.get(mid)
  if prior and prior.get('signature')==signature and (out/target).exists() and sha((out/target).read_bytes())==prior['sha256']:
   entry=prior;reused+=1
  else:
   segs=segment_document(raw.decode('utf-8'),row,identities);stats=collections.Counter(s['kind'] for s in segs);identity_stats=collections.Counter(s.get('identity_status','not_applicable') for s in segs);roles=collections.Counter(s.get('speaker_category','not_applicable') for s in segs)
   document={'schema':VERSION,'processor_sha256':processor_sha,'meeting_id':mid,'term':row['term'],'date':row['date'],'official_url':row['official_url'],'source_path':row['path'],'source_sha256':row['sha256'],'official_content_sha256':row['content_sha256'],'identity_fingerprint':identities.fingerprint,'range_unit':'Unicode codepoints in exact UTF-8-decoded archived Markdown; char_end exclusive; line numbers 1-based inclusive','segments':segs}
   packed=pack(encoded(document));p=out/target;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(packed)
   entry={'meeting_id':mid,'source_sha256':row['sha256'],'signature':signature,'path':target,'sha256':sha(packed),'bytes':len(packed),'segments':len(segs),'paragraphs':sum(len(s['paragraphs']) for s in segs),'kind_counts':dict(stats),'identity_counts':dict(identity_stats),'role_counts':dict(roles)};rebuilt+=1
  if row['date'] in target_dates:
   if segs is None:segs=json.loads(gzip.decompress((out/target).read_bytes()))['segments']
   text=raw.decode('utf-8')
   for seg in segs:
    key=(row['date'],seg.get('speaker_name'))
    if seg.get('person_id') and key in targets:
     haystack=canon(text[seg['content_start']:seg['char_end']])
     for aid,needle in targets[key]:
      found=haystack.find(needle)
      if found>=0:body_evidence[aid].append({'meeting_id':mid,'segment_id':seg['segment_id'],'person_id':seg['person_id'],'term':row['term'],'source_sha256':row['sha256'],'normalized_body_sha256':sha(needle.encode()),'normalized_start':found,'normalized_end':found+len(needle),'method':'entire_activity_body_exact_normalized_substring'})
  catalog.append(entry);counts.update(segments=entry['segments'],paragraphs=entry['paragraphs'],compressed_bytes=entry['bytes']);kinds.update(entry['kind_counts']);links.update(entry['identity_counts']);parsed_roles.update(entry['role_counts'])
 ledger=activity_roles(data,identities,body_evidence);ledger_raw=b''.join(encoded(r) for r in ledger);ledger_packed=pack(ledger_raw);(out/'activity_roles.jsonl.gz').write_bytes(ledger_packed);write_json(out/'meeting_segments_catalog.json',catalog)
 manifest={'schema':'cheongju-processing-manifest/1','processor_version':VERSION,'processor_sha256':processor_sha,'source_meetings':len(rows),'source_index_sha256':sha((root/'indexes/integrated/meetings.json').read_bytes()),'identity_fingerprint':identities.fingerprint,'inputs':{n:mf['datasets'][n] for n in names},'segments':dict(counts),'segment_kinds':dict(kinds),'speaker_categories':dict(parsed_roles),'segment_identity_status':dict(links),'meeting_catalog':{'path':'meeting_segments_catalog.json','sha256':sha((out/'meeting_segments_catalog.json').read_bytes())},'activity_roles':{'path':'activity_roles.jsonl.gz','rows':len(ledger),'source_linked_rows':sum('source_link' in r for r in ledger),'sha256':sha(ledger_packed),'bytes':len(ledger_packed),'kinds':dict(collections.Counter(r['kind'] for r in ledger)),'identity_status':dict(collections.Counter(r['identity_status'] for r in ledger))},'limits':['Speech segments are not classified as questions, answers or procedural/substantive activity.','Speech identities may use unique official roster + explicit meeting term/date/name/role evidence; exact tenure dates remain separately unverified. Activities lacking meeting context still require explicit tenure dates.','Bill role identities preserve the preexisting safe exact-term link; they do not establish exact-date tenure verification.','Cross-source event deduplication, Q/X/P classification and policy follow-up are not implemented.']}
 write_json(out/'manifest.json',manifest)
 report={'status':'PASS','meetings':len(rows),'reused_shards':reused,'rebuilt_shards':rebuilt,**counts,'activity_role_rows':len(ledger),'manifest_sha256':sha((out/'manifest.json').read_bytes())};write_json(root/'reports/processing-latest.json',report);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(process(a.root),ensure_ascii=False,indent=2))
