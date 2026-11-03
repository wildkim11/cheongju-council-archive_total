"""Controller safety/continuity tests: isolated data, no official network."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import automated_collection as a
class AutoCollectionTests(unittest.TestCase):
 def test_rotation_covers_all_families(self):
  s={};self.assertEqual([a.select_family(s,'auto',None) for _ in a.FAMILIES],list(a.FAMILIES))
 def test_missing_board_record_is_preserved(self):
  self.assertEqual(a.preserved_merge([{'source_id':'1'},{'source_id':'2'}],[{'source_id':'2','new':True}],'source_id'),[{'source_id':'1'},{'source_id':'2','new':True}])
 def test_duplicate_discovery_rejected(self):
  with self.assertRaises(ValueError):a.preserved_merge([],[{'source_id':'1'},{'source_id':'1'}],'source_id')
 def fixture(self,r):
  (r/'archive').mkdir();(r/'archive/old.json').write_text('[1]')
 def test_failed_candidate_does_not_modify_original(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.fixture(r)
   def worker(f,s,o):
    (s/'archive/old.json').write_text('[2]');raise RuntimeError('source failed')
   result=a.run(r,'minutes',worker,lambda s,r:{'status':'PASS'})
   self.assertFalse(result['published']);self.assertEqual((r/'archive/old.json').read_text(),'[1]');self.assertTrue((r/'reports/automatic/collection_state.json').exists())
 def test_validator_failure_does_not_publish(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.fixture(r)
   def validator(s,r):raise ValueError('bad hash')
   result=a.run(r,'bills',lambda f,s,o:{},validator);self.assertFalse(result['published'])
 def test_valid_candidate_publishes_with_journal(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.fixture(r)
   def worker(f,s,o):(s/'archive/new.json').write_text('[2]');return {'new':1}
   result=a.run(r,'activities',worker,lambda s,r:{'status':'PASS'});self.assertTrue(result['published']);self.assertTrue((r/'archive/new.json').exists())
 def test_retry_is_durable_and_deferred(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.fixture(r)
   def fail(f,s,o):raise RuntimeError('offline')
   a.run(r,'minutes',fail,lambda s,r:{})
   with patch.object(a,'Capture',side_effect=AssertionError('must not request')):
    self.assertEqual(a.run(r,'minutes',fail,lambda s,r:{})['status'],'DEFERRED')
 def test_capture_preserves_decoded_source(self):
  with tempfile.TemporaryDirectory() as td:
   c=a.Capture(Path(td));self.assertEqual(c.wrap(lambda u:'의회')('https://council.cheongju.go.kr/test'),'의회');p=Path(td)/c.rows[0]['path'];self.assertEqual(a.gzip.decompress(p.read_bytes()).decode(),'의회')
 def test_capture_rejects_unrelated_host(self):
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError):a.Capture(Path(td)).wrap(lambda u:'x')('https://example.com/')
 def test_missing_meetings_rejected_before_export(self):
  with tempfile.TemporaryDirectory() as x,tempfile.TemporaryDirectory() as y:
   old,new=Path(x),Path(y)
   for p in [old,new]:(p/'indexes/integrated').mkdir(parents=True)
   (old/'indexes/integrated/meetings.json').write_text('[{"meeting_id":"1"}]');(new/'indexes/integrated/meetings.json').write_text('[]')
   with self.assertRaisesRegex(ValueError,'saved meetings missing'):a.validate_candidate(new,old)
if __name__=='__main__':unittest.main()
