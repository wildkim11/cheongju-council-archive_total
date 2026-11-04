"""Exercise real local git repositories: code drift is safe, data drift is not."""
import os,shutil,subprocess,tempfile,unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/'scripts/push_collected_snapshot.sh'
class GitCollectionPublishTests(unittest.TestCase):
 def git(self,cwd,*args):return subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True,text=True).stdout.strip()
 def fixture(self,base):
  bare=base/'remote.git';self.git(base,'init','--bare',str(bare));a=base/'collector';self.git(base,'clone',str(bare),str(a));self.git(a,'config','user.name','Test');self.git(a,'config','user.email','test@example.invalid');self.git(a,'checkout','-b','feature/archive-foundation')
  for d in ['archive','scripts','tests']:(a/d).mkdir()
  shutil.copy(SCRIPT.parent/'validate_collection_rebase.py',a/'scripts/validate_collection_rebase.py')
  (a/'archive/source.txt').write_text('old');(a/'scripts/validate_archive.py').write_text('pass');(a/'scripts/audit_stage_c.py').write_text('pass');(a/'tests/test_fixture.py').write_text('import unittest\nfrom pathlib import Path\nclass Fixture(unittest.TestCase):\n def test_source_exists(self):self.assertTrue(Path("archive/source.txt").is_file())\n');self.git(a,'add','.');self.git(a,'commit','-m','initial');self.git(a,'push','-u','origin','feature/archive-foundation')
  b=base/'other';self.git(base,'clone','-b','feature/archive-foundation',str(bare),str(b));self.git(b,'config','user.name','Test');self.git(b,'config','user.email','test@example.invalid');return a,b,bare
 def changed(self,root,path,text):
  (root/path).write_text(text);self.git(root,'add','.');self.git(root,'commit','-m','change')
 def test_code_only_drift_rebased_without_losing_data(self):
  with tempfile.TemporaryDirectory() as td:
   a,b,remote=self.fixture(Path(td));self.changed(a,'archive/source.txt','new collected');self.changed(b,'scripts/new.py','pass');self.git(b,'push');r=subprocess.run(['bash',str(SCRIPT)],cwd=a,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertEqual((a/'archive/source.txt').read_text(),'new collected');self.assertTrue((a/'scripts/new.py').exists())
 def test_concurrent_source_change_is_not_overwritten(self):
  with tempfile.TemporaryDirectory() as td:
   a,b,remote=self.fixture(Path(td));self.changed(a,'archive/source.txt','stale collected');self.changed(b,'archive/source.txt','other accepted snapshot');self.git(b,'push');head=self.git(b,'rev-parse','HEAD');r=subprocess.run(['bash',str(SCRIPT)],cwd=a,capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertIn('REMOTE_SOURCE_SNAPSHOT_CHANGED',r.stderr);self.assertEqual(self.git(remote,'rev-parse','refs/heads/feature/archive-foundation'),head)
if __name__=='__main__':unittest.main()
