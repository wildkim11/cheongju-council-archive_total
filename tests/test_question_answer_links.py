import unittest,sys,tempfile,json,gzip
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import process_meeting_segments as p,resolve_activity_spacing_matches as spacing
import build_question_answer_parts as parts,resolve_question_answer_links as links,verify_processing as verifier
import test_process_meeting_segments as fixtures
class QuestionAnswerLinkTests(unittest.TestCase):
 def fixture(self,root,duplicate=False,answer_duplicate=False,digit_change=False,conflict=False):
  _,row=fixtures.ProcessingIntegrationTests().fixture(root)
  q='의원 질문의 숫자 1234와 문장부호를 그대로 대조합니다. '*12;a='집행부의 답변을 의원의 질문에서 분리하여 보존합니다. '*12
  text='# 회의록\n\n- official_url: '+row['official_url']+'\n\n## ○홍길동 의원  '+q+'\n\n## ○청주시장 김행정  '+a+'\n'
  if answer_duplicate:text+='\n\n## ○청주시장 김행정  '+a+'\n'
  (root/row['path']).write_text(text);_,_,content=p.markdown_parts(text);row.update(sha256=p.sha(text.encode()),content_sha256=p.sha(p.canon(content).encode()));p.write_json(root/'indexes/integrated/meetings.json',[row]);out=root/'exports/analyzer';mf=json.loads((out/'manifest.json').read_text())
  qs=[{'source_id':'1','date':row['date'],'speaker_name':'홍길동','council_scope':'cheongju_integrated','title':'질문','official_url':'https://council.cheongju.go.kr/question/1','body_text':(q.replace('1234','1235')if digit_change else q)+'\n\n'+a}]
  if duplicate:qs.append({**qs[0],'source_id':'2','official_url':'https://council.cheongju.go.kr/question/2'})
  data={'city_questions':qs,'tenures':[{'person_id':'m1','council_scope':'cheongju_integrated','term':4,'start_date':'2030-01-01'if conflict else None,'end_date':None,'source_url':'https://council.cheongju.go.kr/roster'}]}
  for n,rows in data.items():
   raw=b''.join(p.encoded(x)for x in rows);(out/(n+'.jsonl')).write_bytes(raw);mf['datasets'][n]={'rows':len(rows),'sha256':p.sha(raw)}
  p.write_json(out/'manifest.json',mf);p.process(root);spacing.resolve(root);parts.build(root)
 def test_exact_question_and_executive_tail_link_with_independent_verification(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);self.assertEqual(links.resolve(root)['added_links'],1);self.assertEqual(verifier.verify(root)['exact_body_links_verified'],1)
   rows=[json.loads(l)for l in gzip.decompress((root/'exports/processing/activity_roles.jsonl.gz').read_bytes()).splitlines()];self.assertFalse(rows[0]['tenure_interval_verified']);self.assertEqual(rows[0]['identity_status'],'resolved_cross_source_question_answer')
 def test_repeat_does_not_promote_twice(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);self.assertEqual(links.resolve(root)['added_links'],1);self.assertEqual(links.resolve(root)['added_links'],0);self.assertEqual(verifier.verify(root)['exact_body_links_verified'],1)
 def test_duplicate_activity_question_does_not_double_count(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,duplicate=True);self.assertEqual(links.resolve(root)['added_links'],0)
 def test_duplicate_executive_segments_do_not_link(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,answer_duplicate=True);self.assertEqual(links.resolve(root)['added_links'],0)
 def test_changed_digit_not_linked(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,digit_change=True);self.assertEqual(links.resolve(root)['added_links'],0)
 def test_explicit_tenure_conflict_not_overridden(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,conflict=True);self.assertEqual(links.resolve(root)['added_links'],0)
 def corrupt_proof(self,field,value,message):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);links.resolve(root);out=root/'exports/processing';rows=[json.loads(l)for l in gzip.decompress((out/'activity_roles.jsonl.gz').read_bytes()).splitlines()];rows[0]['source_link'][field]=value;raw=p.pack(b''.join(p.encoded(x)for x in rows));(out/'activity_roles.jsonl.gz').write_bytes(raw);mf=json.loads((out/'manifest.json').read_text());mf['activity_roles']['sha256']=p.sha(raw);p.write_json(out/'manifest.json',mf)
   with self.assertRaisesRegex(ValueError,message):verifier.verify(root)
 def test_altered_answer_hash_is_rejected(self):self.corrupt_proof('answer_original_sha256','0'*64,'original hash')
 def test_altered_question_boundary_is_rejected(self):self.corrupt_proof('question_char_end',2,'complete speaker body')
 def test_wrong_answer_source_segment_is_rejected(self):self.corrupt_proof('answer_segment_id','missing','answer segment absent')
if __name__=='__main__':unittest.main()
