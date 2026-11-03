"""Real Git batch checkpoint flow with explicitly synthetic local collectors."""
import datetime as dt,json,subprocess,tempfile,unittest
from pathlib import Path
import test_collection_git_publish as git_fixture
ROOT=Path(__file__).resolve().parents[1]
class BatchCheckpointTests(unittest.TestCase):
 def test_bootstrap_skips_fresh_success_and_checkpoints_after_family_failure(self):
  helper=git_fixture.GitCollectionPublishTests()
  with tempfile.TemporaryDirectory() as td:
   a,b,remote=helper.fixture(Path(td))
   for folder in ('indexes','exports','reports/automatic'):
    (a/folder).mkdir(parents=True,exist_ok=True);(a/folder/'.keep').write_text('')
   (a/'reports/automatic/collection_state.json').write_text(json.dumps({'families':{'minutes':{'last_success_at':dt.datetime.now(dt.timezone.utc).isoformat(),'consecutive_failures':0}}}))
   (a/'scripts/push_collected_snapshot.sh').write_text((ROOT/'scripts/push_collected_snapshot.sh').read_text())
   (a/'scripts/automated_collection.py').write_text("import sys\nfrom pathlib import Path\nf=sys.argv[sys.argv.index('--family')+1]\np=Path('reports/seen.txt');p.write_text((p.read_text() if p.exists() else '')+f+'\\n')\nraise SystemExit(1 if f=='bills' else 0)\n")
   helper.git(a,'add','.');helper.git(a,'commit','-m','synthetic batch fixtures');helper.git(a,'push')
   before=int(helper.git(a,'rev-list','--count','HEAD'));r=subprocess.run(['bash',str(ROOT/'scripts/collect_and_checkpoint.sh'),'bootstrap'],cwd=a,capture_output=True,text=True)
   self.assertEqual(r.returncode,1,r.stderr);self.assertEqual((a/'reports/seen.txt').read_text().splitlines(),['bills','activities','people','groups','media','attachments']);self.assertEqual(int(helper.git(a,'rev-list','--count','HEAD'))-before,6);self.assertEqual(helper.git(a,'rev-parse','HEAD'),helper.git(remote,'rev-parse','refs/heads/feature/archive-foundation'))
if __name__=='__main__':unittest.main()
