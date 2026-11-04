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
 def test_nested_candidate_lock_is_not_published(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.fixture(r)
   def worker(f,s,o):
    (s/a.sync_transaction.LOCK).write_text('temporary candidate lock')
    (s/'archive/new.json').write_text('[2]');return {}
   result=a.run(r,'minutes',worker,lambda s,r:{'status':'PASS'})
   self.assertTrue(result['published']);self.assertTrue((r/'archive/new.json').exists())
 def test_retry_is_durable_and_deferred(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.fixture(r)
   def fail(f,s,o):raise RuntimeError('offline')
   a.run(r,'minutes',fail,lambda s,r:{})
   with patch.object(a,'Capture',side_effect=AssertionError('must not request')):
    self.assertEqual(a.run(r,'minutes',fail,lambda s,r:{})['status'],'DEFERRED')
 def test_deferred_auto_family_does_not_starve_other_sources(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.fixture(r)
   future=(a.dt.datetime.now(a.dt.timezone.utc)+a.dt.timedelta(days=1)).isoformat()
   a.save_json(r/'reports/automatic/collection_state.json',{'cursor':0,'families':{'minutes':{'attempts':1,'next_retry_at':future}}})
   self.assertEqual(a.run(r,'auto',lambda *x:None,lambda *x:None)['status'],'DEFERRED')
   state=a.load(r/'reports/automatic/collection_state.json',{})
   self.assertEqual(state['cursor'],1);self.assertEqual(a.select_family(state,'auto',None),'bills')
 def test_capture_preserves_decoded_source(self):
  with tempfile.TemporaryDirectory() as td:
   c=a.Capture(Path(td));self.assertEqual(c.wrap(lambda u:'의회')('https://council.cheongju.go.kr/test'),'의회');p=Path(td)/c.rows[0]['path'];self.assertEqual(a.gzip.decompress(p.read_bytes()).decode(),'의회')
 def test_source_provenance_survives_next_family(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);c=a.Capture(root);c.wrap(lambda u:'공식 원문')('https://council.cheongju.go.kr/one')
   first=a.preserve_response_manifest(root,'minutes','2026-11-03T00:00:00+00:00',c.rows)
   second=a.preserve_response_manifest(root,'bills','2026-11-03T01:00:00+00:00',c.rows)
   self.assertNotEqual(first,second);self.assertTrue((root/first).is_file())
   self.assertEqual(a.load(root/first,{})['responses'][0]['url'],'https://council.cheongju.go.kr/one')
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

class FailedOnlyRetryTests(unittest.TestCase):
 def test_healthy_retry_never_requests_sources(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td)
   with patch.object(a,'Capture',side_effect=AssertionError('healthy source must not run')):
    self.assertEqual(a.run(r,'minutes',retry_attempt=True)['status'],'DEFERRED')
 def test_document_retry_does_not_fetch_new_pending_files(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);a.save_json(r/'reports/automatic/attachments.json',{'https://council.cheongju.go.kr/download?id=1':{'status':'pending','attempts':0}})
   result=a.download_attachments(r,retry_only=True);self.assertEqual(result['attempted'],0)


class MeetingTextPipelineTests(unittest.TestCase):
 def mocks(self,stack,text_export):
  for name,attr,value in [('export_analyzer','export',{}),('validate_archive','validate',None),('audit_stage_c','audit',{'status':'PASS'}),('process_meeting_segments','process',{}),('resolve_activity_spacing_matches','resolve',{'status':'PASS'}),('verify_processing','verify',{'status':'PASS'}),('review_activity_date_discrepancies','review',{'status':'PASS'}),('build_question_answer_parts','build',{'status':'PASS'}),('resolve_question_answer_links','resolve',{'status':'PASS'}),('review_question_identity_evidence','review',{'status':'PASS'}),('review_single_activity_differences','review',{'status':'PASS'}),('build_activity_temporal_context','build',{'status':'PASS'}),('build_profile_history_evidence','build',{'status':'PASS'}),('build_current_career_evidence','build',{'status':'PASS'}),('build_career_roster_crosswalk','build',{'status':'PASS'}),('audit_nec_election_samples','build',{'status':'PASS'}),('build_analysis_activity_gate','build',{'status':'PASS'}),('build_member_activity_counts','build',{'status':'PASS'}),('build_member_text_inputs','build',{'status':'PASS'}),('build_topic_review_materials','build',{'status':'PASS'}),('build_topic_review_drafts','build',{'status':'PASS'}),('build_topic_review_ui','build',{}),('audit_written_question_links','build',{'status':'PASS'}),('audit_attachment_downloads','build',{'status':'PASS'})]:
   module=__import__(name);stack.enter_context(patch.object(module,attr,return_value=value))
  return stack.enter_context(patch('export_minutes_text.export',side_effect=text_export))
 def test_validated_candidate_exports_text_before_publication(self):
  with tempfile.TemporaryDirectory() as td,a.contextlib.ExitStack() as stack:
   r=Path(td)
   def export(stage):
    a.save_json(stage/'exports/minutes-text/catalog.json',{'schema':'test','rows':1});return {'rows':1}
   mock=self.mocks(stack,export)
   result=a.run(r,'minutes',lambda *args:{})
   self.assertTrue(result['published']);self.assertEqual(result['qa']['minutes_text']['rows'],1)
   self.assertTrue((r/'exports/minutes-text/catalog.json').is_file());mock.assert_called_once()
 def test_text_hash_failure_retains_previous_snapshot(self):
  with tempfile.TemporaryDirectory() as td,a.contextlib.ExitStack() as stack:
   r=Path(td);a.save_json(r/'exports/minutes-text/catalog.json',{'rows':7})
   self.mocks(stack,ValueError('meeting original hash mismatch'))
   result=a.run(r,'minutes',lambda *args:{})
   self.assertFalse(result['published']);self.assertEqual(result['status'],'FAILED')
   self.assertEqual(a.load(r/'exports/minutes-text/catalog.json',{})['rows'],7)
   self.assertIn('hash mismatch',result['error'])
 def test_career_source_hash_failure_retains_previous_snapshot(self):
  with tempfile.TemporaryDirectory() as td,a.contextlib.ExitStack() as stack:
   r=Path(td);a.save_json(r/'archive/people/people.json',[{'person_id':'retained'}])
   self.mocks(stack,lambda stage:{'rows':1})
   stack.enter_context(patch('build_current_career_evidence.build',side_effect=ValueError('career source response hash mismatch')))
   result=a.run(r,'members',lambda *args:{})
   self.assertFalse(result['published']);self.assertEqual(result['status'],'FAILED')
   self.assertEqual(a.load(r/'archive/people/people.json',[]),[{'person_id':'retained'}])
   self.assertIn('career source response hash mismatch',result['error'])


class DateReviewRefreshTests(unittest.TestCase):
 def test_reviewed_dates_are_refreshed_in_normal_board_cycle(self):
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory()as td:
   r=Path(td);a.save_json(r/'archive/activities/five_minute_speeches.json',[{'source_id':'1'},{'source_id':'331'}]);a.save_json(r/'reports/activity-date-discrepancies.json',{'schema':'cheongju-activity-date-review/1','rows':[{'activity_id':'five_minute_speeches:331:speaker','source_dataset':'five_minute_speeches'}]});calls=[]
   cfg={'output':'archive/activities/five_minute_speeches.json','list_url':'https://council.cheongju.go.kr/list','detail_pattern':'unused','section_label':'5분발언'}
   listed=[{'source_id':i,'official_url':'https://council.cheongju.go.kr/'+i}for i in ['1','331','1000']]
   module=SimpleNamespace(__name__='collect_speeches_questions',CONFIG={'five':cfg},discover_links=lambda *args:listed,fetch_text=lambda u:calls.append(u)or'html',parse_detail=lambda text,row,cfg:dict(row))
   result=a.refresh_board(r,module,'five',width=1,ordinal=0)
   self.assertIn('https://council.cheongju.go.kr/331',calls);self.assertEqual(result['review_priority_ids'],['331'])
