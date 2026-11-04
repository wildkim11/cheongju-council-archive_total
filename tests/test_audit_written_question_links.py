import copy,gzip,hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_written_question_links as a
class WrittenLinkAuditTests(unittest.TestCase):
 def setUp(self):
  self.page='https://council.cheongju.go.kr/content/activity/questionLetter.html?number=29';self.row={'source_id':'29','detail_url':self.page,'question_file_url':'https://council.cheongju.go.kr/paper_down.html?number=29&gb=qna','answer_file_url':'https://council.cheongju.go.kr/paper_down.html?number=29&gb=ans'};self.html='<a href="/paper_down.html?number=29&amp;gb=qna">Q</a><a href="/paper_down.html?number=29&amp;gb=ans">A</a><a href="/paper_down.html?number=14&amp;gb=ans">unrelated</a>'
 def fixture(self,root):
  (root/'archive/activities').mkdir(parents=True);(root/'archive/activities/written_questions.json').write_text(json.dumps([self.row]));body=self.html.encode();proof={'url':self.page,'path':'archive/source_responses/response.html.gz','decoded_utf8_sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)};path=root/proof['path'];path.parent.mkdir(parents=True);path.write_bytes(gzip.compress(body));folder=path.parent/'manifests';folder.mkdir();mp=folder/'one.json';mp.write_text(json.dumps({'schema':'cheongju-source-responses/1','family':'activities','collection_started_at':'2026-11-04T06:04:30Z','responses':[proof,proof]}));return path,mp
 def test_exact_current_record_ignores_other_answers(self):self.assertEqual(a.audit_row(self.row,self.html,self.page)['answer_file_url'],self.row['answer_file_url'])
 def test_wrong_record_is_rejected(self):
  r=copy.deepcopy(self.row);r['answer_file_url']=r['answer_file_url'].replace('29','14')
  with self.assertRaisesRegex(ValueError,'wrong record'):a.audit_row(r,self.html,self.page)
 def test_query_smuggling_is_rejected(self):
  r=copy.deepcopy(self.row);r['answer_file_url']+='&number=14'
  with self.assertRaises(ValueError):a.audit_row(r,self.html,self.page)
 def test_external_or_wrong_type_rejected(self):
  for url in [self.row['question_file_url'],self.row['answer_file_url'].replace('council.cheongju.go.kr','example.org')]:
   r=copy.deepcopy(self.row);r['answer_file_url']=url
   with self.assertRaises(ValueError):a.audit_row(r,self.html,self.page)
 def test_ambiguous_versioned_anchors_rejected(self):
  with self.assertRaisesRegex(ValueError,'ambiguous'):a.audit_row(self.row,self.html+'<a href="/paper_down.html?number=29&gb=ans&v=2">A2</a>',self.page)
 def test_duplicate_capture_is_one_proof_not_two_sources(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);r=a.build(root);self.assertEqual(r['verified_records'],1);self.assertFalse(r['attachment_contents_verified']);self.assertEqual(r['official_site_requests'],0)
 def test_tampered_raw_response_is_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);path,_=self.fixture(root);path.write_bytes(gzip.compress(b'tampered'));r=a.build(root);self.assertEqual(r['status'],'HOLD');self.assertIn('hash/size',r['rows'][0]['hold_reason'])
 def test_missing_response_manifest_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);_,mp=self.fixture(root);mp.unlink();self.assertEqual(a.build(root)['held_records'],1)
 def test_unsafe_response_path_is_held(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);_,mp=self.fixture(root);m=json.loads(mp.read_text());m['responses'][0]['path']='../outside.gz';m['responses']=m['responses'][:1];mp.write_text(json.dumps(m));self.assertIn('unsafe',a.build(root)['rows'][0]['hold_reason'])
if __name__=='__main__':unittest.main()
