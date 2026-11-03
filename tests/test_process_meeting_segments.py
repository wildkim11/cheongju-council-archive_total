"""Evidence/range/identity invariants; fixtures are synthetic and offline."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import process_meeting_segments as p
class SegmentTests(unittest.TestCase):
 def identities(self,dated=True,extra=False):
  people=[{'person_id':'m1','name':'홍길동'},{'person_id':'m2','name':'김의원'}]
  tenures=[{'person_id':'m1','council_scope':'cheongju_integrated','term':4,'start_date':'2026-07-01' if dated else None,'end_date':'2030-06-30' if dated else None}]
  if extra:
   people.append({'person_id':'m3','name':'홍길동'});tenures.append({'person_id':'m3','council_scope':'cheongju_integrated','term':4,'start_date':None,'end_date':None})
  return p.Identities(people,tenures)
 def source(self):
  text='# 회의록\n\n- official_url: https://councilrec.cheongju.go.kr/1\n\n회의의 시작\n\n## ○홍길동 위원 \u2003자료를 확인해 주십시오.\n\n추가 발언입니다.\n\n## ○기획예산과장 홍길동\u3000예, 확인하겠습니다.\n\n## ○출석 위원(1명)\n홍길동\n'
  _,_,body=p.markdown_parts(text);row={'meeting_id':'m:1','term':4,'date':'2026-11-03','council_scope':'cheongju_integrated','official_url':'https://councilrec.cheongju.go.kr/1','path':'archive/meetings/m1.md','sha256':p.sha(text.encode()),'content_sha256':p.sha(p.canon(body).encode())};return text,row
 def test_emspace_and_name_first(self):
  x=p.parse_label('## ○홍길동 위원 \u2003발언');self.assertEqual(x['speaker_name'],'홍길동');self.assertEqual(x['speaker_category'],'council_member')
 def test_role_first_and_ascii_fallback(self):
  x=p.parse_label('## ○위원장 홍길동 발언입니다.');self.assertEqual(x['speaker_name'],'홍길동');self.assertEqual(x['speaker_category'],'council_presiding')
 def test_attendance_is_not_a_speech(self):self.assertIsNone(p.parse_label('## ○출석 위원(7명)'))
 def test_staff_not_mapped_to_same_named_member(self):
  text,row=self.source();segments=p.segment_document(text,row,self.identities());staff=[s for s in segments if s.get('speaker_role')=='기획예산과장'][0];self.assertIsNone(staff['person_id']);self.assertEqual(staff['identity_status'],'not_a_council_speaker')
 def test_exact_source_coverage_and_paragraph_hashes(self):
  text,row=self.source();segs=p.segment_document(text,row,self.identities());self.assertEqual(''.join(text[s['char_start']:s['char_end']] for s in segs),text.split('\n\n',2)[2])
  for s in segs:
   for part in s['paragraphs']:self.assertEqual(part['text_sha256'],p.sha(text[part['char_start']:part['char_end']].encode()))
 def test_speaker_not_automatically_a_question(self):
  text,row=self.source();segs=p.segment_document(text,row,self.identities());self.assertTrue(all(s['speech_function']=='unclassified' for s in segs if s['kind']=='speech'))
 def test_undated_identity_kept_as_candidate(self):
  x=self.identities(False).resolve('홍길동','cheongju_integrated','2026-11-03',4);self.assertIsNone(x['person_id']);self.assertEqual(x['candidate_person_ids'],['m1'])
 def test_explicit_dates_resolve(self):self.assertEqual(self.identities().resolve('홍길동','cheongju_integrated','2026-11-03',4)['person_id'],'m1')
 def test_same_term_unknown_competitor_not_silently_merged(self):self.assertIsNone(self.identities(extra=True).resolve('홍길동','cheongju_integrated','2026-11-03',4)['person_id'])
 def test_outside_explicit_dates_not_assigned(self):self.assertEqual(self.identities().resolve('홍길동','cheongju_integrated','2020-01-01',4)['identity_status'],'outside_known_tenure')
 def test_wrong_scope_and_term_not_joined(self):
  for scope,term in [('other',4),('cheongju_integrated',3)]:self.assertIsNone(self.identities().resolve('홍길동',scope,'2026-11-03',term)['person_id'])
 def test_source_content_corruption_rejected(self):
  text,row=self.source()
  with self.assertRaisesRegex(ValueError,'content hash'):p.segment_document(text+'변조',row,self.identities())
 def test_one_non_speech_body_preserved(self):
  text,row=self.source();text=text[:text.index('회의의 시작')]+'개의되지 않음\n';_,_,body=p.markdown_parts(text);row['content_sha256']=p.sha(p.canon(body).encode());segs=p.segment_document(text,row,self.identities());self.assertEqual(len(segs),1);self.assertEqual(segs[0]['kind'],'preamble')
 def test_gzip_reproducible(self):self.assertEqual(p.pack(b'preserved source'),p.pack(b'preserved source'))

class ProcessingIntegrationTests(unittest.TestCase):
 source=SegmentTests.source
 def fixture(self,root):
  text,row=self.source();(root/'archive/meetings').mkdir(parents=True);(root/'archive/meetings/m1.md').write_text(text);(root/'indexes/integrated').mkdir(parents=True);(root/'indexes/integrated/meetings.json').write_text(json.dumps([row]));exports=root/'exports/analyzer';exports.mkdir(parents=True)
  inputs={'people':[{'person_id':'m1','name':'홍길동'}],'tenures':[{'person_id':'m1','council_scope':'cheongju_integrated','term':4,'start_date':'2026-07-01','end_date':'2030-06-30'}],'bills':[],'bill_proposers_member_only':[],'five_minute_speeches':[],'city_questions':[],'written_questions':[]};mf={'datasets':{}}
  for name,rows in inputs.items():
   raw=b''.join(p.encoded(x) for x in rows);(exports/(name+'.jsonl')).write_bytes(raw);mf['datasets'][name]={'rows':len(rows),'sha256':p.sha(raw)}
  (exports/'manifest.json').write_text(json.dumps(mf));return text,row
 def test_repeat_uses_identical_cached_shard_and_manifest(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.fixture(root);first=p.process(root);before=(root/'exports/processing/manifest.json').read_bytes();second=p.process(root);self.assertEqual(first['rebuilt_shards'],1);self.assertEqual(second['reused_shards'],1);self.assertEqual(before,(root/'exports/processing/manifest.json').read_bytes())
 def test_corrupt_cache_is_rebuilt_from_verified_source(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.fixture(root);p.process(root);catalog=json.loads((root/'exports/processing/meeting_segments_catalog.json').read_text());target=root/'exports/processing'/catalog[0]['path'];original=target.read_bytes();target.write_bytes(b'bad cache');result=p.process(root);self.assertEqual(result['rebuilt_shards'],1);self.assertEqual(target.read_bytes(),original)
 def test_corrupt_original_never_reuses_prior_cache(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.fixture(root);p.process(root);before=(root/'exports/processing/manifest.json').read_bytes();(root/'archive/meetings/m1.md').write_text('bad source')
   with self.assertRaisesRegex(ValueError,'original hash'):p.process(root)
   self.assertEqual(before,(root/'exports/processing/manifest.json').read_bytes())
 def test_bad_input_export_is_rejected_before_processing(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.fixture(root);(root/'exports/analyzer/people.jsonl').write_text('{}\n')
   with self.assertRaisesRegex(ValueError,'input export hash'):p.process(root)

class ContextIdentityTests(unittest.TestCase):
 def test_official_meeting_context_links_unique_term_roster_but_not_dates(self):
  people=[{'person_id':'m','name':'홍길동'}];ten=[{'person_id':'m','council_scope':'cheongju_integrated','term':4,'start_date':None,'end_date':None,'source_url':'https://council.cheongju.go.kr/roster'}];ids=p.Identities(people,ten);ctx={'meeting_id':'m1','term':4,'date':'2026-11-03','council_scope':'cheongju_integrated','official_url':'https://councilrec.cheongju.go.kr/minutes/1','sha256':'a'*64}
  self.assertIsNone(ids.resolve('홍길동','cheongju_integrated','2026-11-03',4)['person_id'])
  x=ids.resolve('홍길동','cheongju_integrated','2026-11-03',4,meeting_context=ctx);self.assertEqual(x['person_id'],'m');self.assertEqual(x['identity_status'],'resolved_source_meeting_term');self.assertFalse(x['tenure_interval_verified'])
 def test_meeting_context_does_not_override_explicit_tenure_conflict(self):
  ids=SegmentTests().identities();_,ctx=SegmentTests().source();ctx['date']='2020-01-01';self.assertIsNone(ids.resolve('홍길동','cheongju_integrated','2020-01-01',4,meeting_context=ctx)['person_id'])
 def test_duplicate_same_term_people_remain_ambiguous(self):
  ids=SegmentTests().identities(False,True);_,ctx=SegmentTests().source();self.assertIsNone(ids.resolve('홍길동','cheongju_integrated','2026-11-03',4,meeting_context=ctx)['person_id'])

class ActivityEvidenceTests(unittest.TestCase):
 def data(self):return {'people':[],'tenures':[],'bills':[],'bill_proposers_member_only':[],'five_minute_speeches':[{'source_id':'1','date':'2026-11-03','speaker_name':'홍길동','council_scope':'cheongju_integrated','title':'발언','official_url':'https://council.cheongju.go.kr/one'}],'city_questions':[],'written_questions':[]}
 def proof(self):return {'person_id':'m1','term':4,'meeting_id':'m1','segment_id':'s1'}
 def test_only_one_exact_body_source_can_resolve_undated_activity(self):
  x=p.activity_roles(self.data(),SegmentTests().identities(False),{'five_minute_speeches:1':[self.proof()]})[0];self.assertEqual(x['person_id'],'m1');self.assertEqual(x['identity_status'],'resolved_cross_source_exact_body');self.assertFalse(x['tenure_interval_verified'])
 def test_multiple_matching_segments_are_not_arbitrarily_selected(self):
  x=p.activity_roles(self.data(),SegmentTests().identities(False),{'five_minute_speeches:1':[self.proof(),{**self.proof(),'segment_id':'s2'}]})[0];self.assertIsNone(x['person_id'])
 def test_source_body_match_does_not_override_dated_identity_conflict(self):
  x=p.activity_roles(self.data(),SegmentTests().identities(),{'five_minute_speeches:1':[{**self.proof(),'person_id':'other'}]})[0];self.assertIsNone(x['person_id']);self.assertEqual(x['identity_status'],'identity_evidence_conflict')
