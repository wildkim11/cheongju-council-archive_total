import gzip,hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import export_minutes_text as e
class TextExportTests(unittest.TestCase):
 def fixture(self,r):
  body='○의원 가\n공식 회의록 내용입니다.';raw=('# 회의록\n\n- date: 2026-01-01\n\n'+body+'\n').encode();p=r/'archive/meetings/term-4/test.md';p.parent.mkdir(parents=True);p.write_bytes(raw);(r/'indexes/integrated').mkdir(parents=True);row={'meeting_id':'m1','term':4,'date':'2026-01-01','official_url':'https://councilrec.cheongju.go.kr/minutes/1','publication_status':'published','path':str(p.relative_to(r)),'sha256':e.sha(raw),'content_sha256':e.sha(e.canon(body).encode())};(r/'indexes/integrated/meetings.json').write_text(json.dumps([row]));return row,p
 def test_text_and_link_roundtrip(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);row,p=self.fixture(r);c=e.export(r);part=r/'exports/minutes-text'/c['parts'][0]['file'];data=json.loads(gzip.decompress(part.read_bytes()));self.assertEqual(data['official_url'],row['official_url']);self.assertIn('공식 회의록',data['text']);self.assertEqual(c['rows'],1)
 def test_deterministic_compressed_bytes(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.fixture(r);a=e.export(r);b=e.export(r);self.assertEqual(a,b)
 def test_bad_original_cannot_publish_text(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);row,p=self.fixture(r);p.write_text('corrupted')
   with self.assertRaisesRegex(ValueError,'original hash'):e.export(r)
   self.assertFalse((r/'exports/minutes-text/catalog.json').exists())
 def test_bad_body_hash_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);row,p=self.fixture(r);row['content_sha256']='0'*64;(r/'indexes/integrated/meetings.json').write_text(json.dumps([row]))
   with self.assertRaisesRegex(ValueError,'body hash'):e.export(r)
if __name__=='__main__':unittest.main()
