import gzip,json,sys,tempfile,unittest
from pathlib import Path
import test_process_meeting_segments as fixtures
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import process_meeting_segments as p,verify_processing as v
class DerivedEvidenceTests(unittest.TestCase):
 def test_verified_source_and_ledger(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);fixtures.ProcessingIntegrationTests().fixture(root);p.process(root);r=v.verify(root);self.assertEqual(r['verified_originals'],1);self.assertEqual(r['status'],'PASS')
 def test_wrong_ranges_rejected_even_after_rehashing_output(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);fixtures.ProcessingIntegrationTests().fixture(root);p.process(root);out=root/'exports/processing';cat=json.loads((out/'meeting_segments_catalog.json').read_text());path=out/cat[0]['path'];doc=json.loads(gzip.decompress(path.read_bytes()));doc['segments'][0]['char_end']+=1;raw=p.pack(p.encoded(doc));path.write_bytes(raw);cat[0].update(sha256=p.sha(raw),bytes=len(raw));p.write_json(out/'meeting_segments_catalog.json',cat);mf=json.loads((out/'manifest.json').read_text());mf['meeting_catalog']['sha256']=p.sha((out/'meeting_segments_catalog.json').read_bytes());p.write_json(out/'manifest.json',mf)
   with self.assertRaisesRegex(ValueError,'mismatch'):v.verify(root)

class ExactBodyIntegrationTests(unittest.TestCase):
 def test_only_full_body_evidence_resolves_and_changed_body_removes_stale_link(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);text,row=fixtures.ProcessingIntegrationTests().fixture(root);body='공식 발언 원문으로 교차 대조합니다. '*10;text=text.replace('자료를 확인해 주십시오.',body);(root/row['path']).write_text(text);_,_,content=p.markdown_parts(text);row.update(sha256=p.sha(text.encode()),content_sha256=p.sha(p.canon(content).encode()));(root/'indexes/integrated/meetings.json').write_text(json.dumps([row]));exports=root/'exports/analyzer';mf=json.loads((exports/'manifest.json').read_text())
   def write(name,rows):
    raw=b''.join(p.encoded(x) for x in rows);(exports/(name+'.jsonl')).write_bytes(raw);mf['datasets'][name]={'rows':len(rows),'sha256':p.sha(raw)};(exports/'manifest.json').write_text(json.dumps(mf))
   write('tenures',[{'person_id':'m1','council_scope':'cheongju_integrated','term':4,'start_date':None,'end_date':None,'source_url':'https://council.cheongju.go.kr/roster'}]);activity={'source_id':'1','date':row['date'],'speaker_name':'홍길동','council_scope':'cheongju_integrated','title':'발언','official_url':'https://council.cheongju.go.kr/activity/1','body_text':body};write('five_minute_speeches',[activity]);p.process(root);self.assertEqual(v.verify(root)['exact_body_links_verified'],1)
   activity['body_text']='원문에 없는 다른 발언 내용입니다. '*10;write('five_minute_speeches',[activity]);p.process(root);self.assertEqual(v.verify(root)['exact_body_links_verified'],0);ledger=json.loads(gzip.decompress((root/'exports/processing/activity_roles.jsonl.gz').read_bytes()));self.assertIsNone(ledger['person_id'])
