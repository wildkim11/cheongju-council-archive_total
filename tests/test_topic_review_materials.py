import unittest,tempfile,sys,json,gzip,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_topic_review_materials as b
from process_meeting_segments import sha,encoded,pack,write_json
class TopicReviewTests(unittest.TestCase):
 def record(self,i=1,term=1,dataset='five_minute_speeches'):
  text='주민의 이동권을 보장하기 위한 버스 정책을 제안합니다.'
  return {'activity_id':f'{dataset}:{i}:speaker','person_id':f'p{i%5}','person_name':'의원','term':term,'date':'2026-01-01','source_dataset':dataset,'activity_url':'https://council.cheongju.go.kr/record','source_content_proofs':[{'segment_id':f's{i}'}],'text_input_eligible':True,'hold_reasons':[],'member_text':text,'member_text_sha256':sha(text.encode())}
 def book(self):return {'schema':'cheongju-policy-topic-codebook/1','version':'v1','topics':[dict(id='CJ10',definition='교통',include='버스',exclude='인사',positive_example='교통 정책',negative_example='인사말')]}
 def fixture(self,root,records):
  (root/'config').mkdir();write_json(root/'config/policy_topics_v1.json',self.book());p=root/'exports/processing';p.mkdir(parents=True);raw=pack(b''.join(encoded(r)for r in records));(p/'input.gz').write_bytes(raw);write_json(p/'member_text_inputs_manifest.json',{'schema':'cheongju-member-text-input-release/1','outputs':{'eligible':{'file':'input.gz','rows':len(records),'bytes':len(raw),'sha256':sha(raw)}}})
 def annotation(self,r):
  return {'activity_id':r['activity_id'],'member_text_sha256':r['member_text_sha256'],'codebook_sha256':'hash','status':'completed','review_origin':'human','reviewer_id':'reviewer-A','decision':'coded','topic_ids':['CJ10'],'rationale':'이동 정책을 제안한다','evidence_spans':[{'topic_id':'CJ10','start':0,'end':2,'quote':r['member_text'][:2]}]}
 def test_reproducible_balanced_sample_with_questions(self):
  rows=[self.record(i,1+(i%4))for i in range(40)]+[self.record(100+i,1+(i%3),'city_questions')for i in range(13)];a=b.sample(rows);random.Random(7).shuffle(rows);self.assertEqual([r['activity_id']for r in a],[r['activity_id']for r in b.sample(rows)]);self.assertEqual(len(a),40);self.assertEqual(sum(r['source_dataset']=='city_questions'for r in a),13);self.assertEqual(len({r['activity_id']for r in a}),40)
 def test_materials_reproduce_and_never_assign_labels(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,[self.record()]);result=b.build(root);self.assertEqual(result['completed_human_reviews'],0);self.assertEqual(result['topic_assignments_computed'],0);before=(root/'exports/topic-review/manifest.json').read_bytes();b.build(root);self.assertEqual(before,(root/'exports/topic-review/manifest.json').read_bytes());r=json.loads(gzip.decompress((root/'exports/topic-review/development_sample.jsonl.gz').read_bytes()).splitlines()[0]);self.assertIsNone(r['topic_ids']);self.assertIsNone(r['reviewer_id'])
 def test_candidate_can_use_explicit_versioned_codebook(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,[self.record()]);book=root/'policy.json';(root/'config/policy_topics_v1.json').rename(book);self.assertEqual(b.build(root,codebook_path=book)['eligible_source_records'],1)
 def test_corrupt_input_hash_rejected(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,[self.record()]);(root/'exports/processing/input.gz').write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'hash/size'):b.build(root)
 def test_held_record_never_enters_review(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);r=self.record();r['text_input_eligible']=False;self.fixture(root,[r])
   with self.assertRaisesRegex(ValueError,'unverified text'):b.build(root)
 def test_completed_review_requires_exact_span(self):
  r=self.record();self.assertTrue(b.validate_annotation(self.annotation(r),r,self.book(),'hash'))
 def test_quote_mismatch_rejected(self):
  r=self.record();a=self.annotation(r);a['evidence_spans'][0]['quote']='다름'
  with self.assertRaisesRegex(ValueError,'exact source'):b.validate_annotation(a,r,self.book(),'hash')
 def test_stale_source_rejected(self):
  r=self.record();a=self.annotation(r);a['member_text_sha256']='old'
  with self.assertRaisesRegex(ValueError,'version mismatch'):b.validate_annotation(a,r,self.book(),'hash')
 def test_stale_codebook_rejected(self):
  r=self.record();a=self.annotation(r)
  with self.assertRaisesRegex(ValueError,'version mismatch'):b.validate_annotation(a,r,self.book(),'new-hash')
 def test_unknown_topic_rejected(self):
  r=self.record();a=self.annotation(r);a['topic_ids']=['CJ99']
  with self.assertRaisesRegex(ValueError,'topic labels'):b.validate_annotation(a,r,self.book(),'hash')
 def test_label_without_evidence_rejected(self):
  r=self.record();a=self.annotation(r);a['evidence_spans']=[]
  with self.assertRaisesRegex(ValueError,'lacks source evidence'):b.validate_annotation(a,r,self.book(),'hash')
 def test_unreviewed_or_automated_not_a_completed_human_reference(self):
  r=self.record();a=self.annotation(r);a['status']='unreviewed'
  with self.assertRaisesRegex(ValueError,'not completed'):b.validate_annotation(a,r,self.book(),'hash')
  a=self.annotation(r);a['review_origin']='automated'
  with self.assertRaisesRegex(ValueError,'not completed'):b.validate_annotation(a,r,self.book(),'hash')
if __name__=='__main__':unittest.main()
