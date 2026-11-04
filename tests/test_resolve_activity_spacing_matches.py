import json,gzip,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import process_meeting_segments as p,resolve_activity_spacing_matches as s,verify_processing as v
import test_process_meeting_segments as fixtures
class SpacingMatchesTests(unittest.TestCase):
 def fixture(self,root,duplicate=False):
  text,row=fixtures.ProcessingIntegrationTests().fixture(root);body='공식 발언 원문의 모든 글자와 문장부호를 그대로 확인합니다. '*8;spaced=' '.join(''.join(body.split()));text=text.replace('자료를 확인해 주십시오.',spaced)
  if duplicate:text+='\n\n○홍길동 의원  '+spaced+'\n'
  (root/row['path']).write_text(text);_,_,content=p.markdown_parts(text);row.update(sha256=p.sha(text.encode()),content_sha256=p.sha(p.canon(content).encode()));(root/'indexes/integrated/meetings.json').write_text(json.dumps([row]));out=root/'exports/analyzer';mf=json.loads((out/'manifest.json').read_text());inputs={'tenures':[{'person_id':'m1','council_scope':'cheongju_integrated','term':4,'start_date':None,'end_date':None,'source_url':'https://council.cheongju.go.kr/roster'}],'five_minute_speeches':[{'source_id':'1','date':row['date'],'speaker_name':'홍길동','council_scope':'cheongju_integrated','title':'발언','official_url':'https://council.cheongju.go.kr/activity/1','body_text':body}]}
  for name,rows in inputs.items():
   raw=b''.join(p.encoded(x)for x in rows);(out/(name+'.jsonl')).write_bytes(raw);mf['datasets'][name]={'rows':len(rows),'sha256':p.sha(raw)}
  (out/'manifest.json').write_text(json.dumps(mf));return body
 def test_full_spacing_difference_links_with_independent_verification(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);p.process(root);self.assertEqual(s.resolve(root)['added_links'],1);self.assertEqual(v.verify(root)['exact_body_links_verified'],1)
 def test_same_date_duplicate_segments_remain_unassigned(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,True);p.process(root);r=s.resolve(root);self.assertEqual(r['added_links'],0);self.assertEqual(r['diagnosis_counts']['ambiguous_complete_matches'],1)
 def test_cached_segments_reused_after_ledger_enrichment(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);p.process(root);s.resolve(root);self.assertEqual(p.process(root)['reused_shards'],1)
 def test_short_body_never_matches(self):self.assertIsNone(s.match('짧은 발언','짧은 발언'))
 def test_numeric_digit_gap_preserved(self):self.assertNotEqual(s.compact('예산 1 2억원'),s.compact('예산 12억원'))
 def test_decimal_and_thousands_punctuation_preserved(self):
  for a,b in [('1.2','12'),('1,200','1200'),('1-2','12')]:self.assertIsNone(s.match(('금액'+a+'억원입니다.')*12,('금액'+b+'억원입니다.')*12))
 def test_words_and_negation_never_removed(self):self.assertIsNone(s.match('동의하지 않습니다.'*20,'동의합니다.'*20))
 def test_activity_raw_body_hash_tamper_rejected(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);p.process(root);s.resolve(root);out=root/'exports/processing';rows=[json.loads(l)for l in gzip.decompress((out/'activity_roles.jsonl.gz').read_bytes()).splitlines()];rows[0]['source_link']['activity_body_sha256']='0'*64;raw=p.pack(b''.join(p.encoded(x)for x in rows));(out/'activity_roles.jsonl.gz').write_bytes(raw);mf=json.loads((out/'manifest.json').read_text());mf['activity_roles']['sha256']=p.sha(raw);p.write_json(out/'manifest.json',mf)
   with self.assertRaisesRegex(ValueError,'original body hash'):v.verify(root)
