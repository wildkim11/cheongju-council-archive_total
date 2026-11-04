import json,tempfile,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import process_meeting_segments as p,resolve_activity_spacing_matches as s,review_activity_date_discrepancies as d
import test_resolve_activity_spacing_matches as fixtures
class DateReviewTests(unittest.TestCase):
 def fixture(self,root,duplicate=False):
  fixtures.SpacingMatchesTests().fixture(root,duplicate);exports=root/'exports/analyzer';path=exports/'five_minute_speeches.jsonl';row=json.loads(path.read_text());row['date']='2026-11-04';raw=p.encoded(row);path.write_bytes(raw);mf=json.loads((exports/'manifest.json').read_text());mf['datasets']['five_minute_speeches']['sha256']=p.sha(raw);(exports/'manifest.json').write_text(json.dumps(mf));p.process(root);s.resolve(root)
 def test_cross_date_review_preserves_role_ledger_and_source_date(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);path=root/'exports/processing/activity_roles.jsonl.gz';before=path.read_bytes();r=d.review(root);self.assertEqual(r['date_changes'],0);self.assertEqual(r['identity_promotions'],0);self.assertEqual(r['diagnosis_counts']['unique_cross_date_complete_body_match_review'],1);self.assertEqual(before,path.read_bytes());saved=json.loads((root/'reports/activity-date-discrepancies.json').read_text())['rows'][0];self.assertEqual(saved['source_display_date'],'2026-11-04');self.assertEqual(saved['candidates'][0]['meeting_date'],'2026-11-03')
 def test_multiple_matching_speeches_are_reviewed_as_ambiguous(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root,True);self.assertEqual(d.review(root)['diagnosis_counts']['ambiguous_cross_date_matches'],1)
 def test_corrupt_activity_input_rejected(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);self.fixture(root);(root/'exports/processing/activity_roles.jsonl.gz').write_bytes(b'bad')
   with self.assertRaisesRegex(ValueError,'hash'):d.review(root)
 def test_same_date_not_reported_as_date_discrepancy(self):
  a={'date':'2026-01-01'};source={'council_scope':'scope'};m={'council_scope':'scope','date':'2026-01-01'};self.assertIsNone(d.candidate(a,source,m,{},''))
 def test_different_scope_never_matches(self):self.assertIsNone(d.candidate({'date':'x'},{'council_scope':'A'},{'council_scope':'B','date':'y'},{},''))
 def test_external_speaker_not_candidate(self):self.assertIsNone(d.candidate({'date':'x','person_name':'홍길동'},{'council_scope':'A'},{'council_scope':'A','date':'y'},{'speaker_name':'홍길동','speaker_category':'executive_or_staff','person_id':'p'},''))
 def test_inconsistent_identity_candidate_not_used(self):self.assertIsNone(d.candidate({'date':'x','person_name':'홍길동','candidate_person_ids':['other']},{'council_scope':'A'},{'council_scope':'A','date':'y'},{'speaker_name':'홍길동','speaker_category':'council_member','person_id':'p'},''))
