import json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate_collection_rebase import validate_paths
class RebasePolicyTests(unittest.TestCase):
 def test_code_and_documentation_allowed(self):self.assertTrue(validate_paths(['scripts/x.py','docs/x.md'],['archive/media.json']))
 def test_isolated_audit_report_allowed(self):self.assertTrue(validate_paths(['reports/written-question-link-audit.json'],['archive/media.json']))
 def test_archived_source_rejected_even_when_disjoint(self):
  with self.assertRaisesRegex(ValueError,'SNAPSHOT_CHANGED'):validate_paths(['archive/other.json'],['archive/media.json'])
 def test_arbitrary_report_rejected(self):
  with self.assertRaises(ValueError):validate_paths(['reports/automatic/collection_state.json'],['archive/media.json'])
 def test_exports_rejected(self):
  with self.assertRaises(ValueError):validate_paths(['exports/data.json'],[])
 def test_same_report_conflict_rejected(self):
  with self.assertRaisesRegex(ValueError,'OVERLAP'):validate_paths(['reports/written-question-link-audit.json'],['reports/written-question-link-audit.json'])
 def test_same_code_conflict_rejected(self):
  with self.assertRaises(ValueError):validate_paths(['scripts/x.py'],['scripts/x.py'])
 def test_fake_report_prefix_rejected(self):
  with self.assertRaises(ValueError):validate_paths(['reports/written-question-link-audit.json/other'],[])
class PushIntegrationTests(unittest.TestCase):
 def git(self,root,*args,check=True):return subprocess.run(['git',*args],cwd=root,check=check,capture_output=True,text=True)
 def fixture(self,root):
  origin=root/'origin.git';self.git(root,'init','--bare',str(origin));seed=root/'seed';seed.mkdir();self.git(seed,'init');self.git(seed,'config','user.email','test@example.invalid');self.git(seed,'config','user.name','test');self.git(seed,'checkout','-b','feature/archive-foundation');(seed/'scripts').mkdir();(seed/'tests').mkdir();(seed/'archive').mkdir();(seed/'reports').mkdir()
  source=Path(__file__).resolve().parents[1]/'scripts'
  for name in ['push_collected_snapshot.sh','validate_collection_rebase.py']:shutil.copy(source/name,seed/'scripts'/name)
  for name in ['validate_archive.py','audit_stage_c.py']:(seed/'scripts'/name).write_text('pass\n')
  (seed/'scripts/audit_written_question_links.py').write_text("from pathlib import Path\nPath('AUDIT_CALLED').touch()\n")
  (seed/'tests/test_smoke.py').write_text('import unittest\nclass Smoke(unittest.TestCase):\n def test_ok(self):self.assertTrue(True)\n');(seed/'archive/media.json').write_text('old');self.git(seed,'add','.');self.git(seed,'commit','-m','baseline');self.git(seed,'remote','add','origin',str(origin));self.git(seed,'push','origin','HEAD:feature/archive-foundation')
  copies=[]
  for name in ['collector','editor']:
   dest=root/name;self.git(root,'clone','-b','feature/archive-foundation',str(origin),str(dest));self.git(dest,'config','user.email','test@example.invalid');self.git(dest,'config','user.name','test');copies.append(dest)
  collector,editor=copies;(collector/'archive/media.json').write_text('new media');self.git(collector,'add','.');self.git(collector,'commit','-m','data: collected media');return origin,collector,editor
 def test_isolated_report_rebases_and_preserves_both(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);origin,collector,editor=self.fixture(root);(editor/'reports').mkdir(exist_ok=True);(editor/'reports/written-question-link-audit.json').write_text('{}');self.git(editor,'add','.');self.git(editor,'commit','-m','audit');self.git(editor,'push');result=subprocess.run(['bash','scripts/push_collected_snapshot.sh'],cwd=collector,text=True,capture_output=True);self.assertEqual(result.returncode,0,result.stderr);self.assertTrue((collector/'AUDIT_CALLED').exists());self.assertEqual(self.git(root,'--git-dir',str(origin),'show','feature/archive-foundation:archive/media.json').stdout,'new media');self.assertEqual(self.git(root,'--git-dir',str(origin),'show','feature/archive-foundation:reports/written-question-link-audit.json').stdout,'{}')
 def test_concurrent_source_snapshot_never_pushed(self):
  with tempfile.TemporaryDirectory()as td:
   root=Path(td);origin,collector,editor=self.fixture(root);(editor/'archive/other.json').write_text('other snapshot');self.git(editor,'add','.');self.git(editor,'commit','-m','other source');self.git(editor,'push');before=self.git(root,'--git-dir',str(origin),'rev-parse','feature/archive-foundation').stdout;result=subprocess.run(['bash','scripts/push_collected_snapshot.sh'],cwd=collector,text=True,capture_output=True);self.assertNotEqual(result.returncode,0);self.assertIn('SNAPSHOT_CHANGED',result.stderr);self.assertEqual(self.git(root,'--git-dir',str(origin),'rev-parse','feature/archive-foundation').stdout,before);self.assertEqual(self.git(root,'--git-dir',str(origin),'show','feature/archive-foundation:archive/media.json').stdout,'old')
if __name__=='__main__':unittest.main()
