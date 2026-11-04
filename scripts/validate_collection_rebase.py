"""Permit isolated code/audit updates, while rejecting concurrent source snapshots."""
import subprocess
CODE_PREFIXES=('scripts/','tests/','docs/','.github/')
ISOLATED_REPORTS={'reports/written-question-link-audit.json'}
def validate_paths(remote_paths,collected_paths):
 remote=set(remote_paths);local=set(collected_paths)
 if any(not(p.startswith(CODE_PREFIXES)or p in ISOLATED_REPORTS)for p in remote):raise ValueError('REMOTE_SOURCE_SNAPSHOT_CHANGED: recollect instead of overwriting another snapshot')
 if remote&local:raise ValueError('REMOTE_COLLECTION_PATH_OVERLAP: concurrent edits require review')
 return True
def changed(base,tip):
 raw=subprocess.check_output(['git','diff','--name-only','-z',base,tip]);return [p.decode('utf-8')for p in raw.split(b'\0')if p]
if __name__=='__main__':
 try:
  subprocess.run(['git','merge-base','--is-ancestor','HEAD~1',__import__('sys').argv[1]],check=True,capture_output=True)
  validate_paths(changed('HEAD~1',__import__('sys').argv[1]),changed('HEAD~1','HEAD'))
 except (ValueError,subprocess.CalledProcessError)as error:raise SystemExit(str(error))
