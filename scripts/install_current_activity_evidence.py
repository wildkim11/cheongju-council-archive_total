"""Install a read-only Stage47 projection without changing embedded datasets."""
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
START='// BEGIN COUNCIL_CURRENT_ACTIVITY_EVIDENCE'
END='// END COUNCIL_CURRENT_ACTIVITY_EVIDENCE'
BOOT='readStore();render();window.councilBootReady();'
def install(html,code):
 if html.count(BOOT)!=1 or 'function dataVersionsPanel()' not in html:
  raise ValueError('unknown Stage47 startup or missing versions module')
 if '</script' in code.lower():raise ValueError('unsafe script terminator')
 block=START+'\n'+code.rstrip()+'\n'+END
 if START in html or END in html:
  if html.count(START)!=1 or html.count(END)!=1 or html.index(START)>html.index(END):
   raise ValueError('ambiguous current-evidence markers')
  start=html.index(START);end=html.index(END)+len(END)
  if end>html.index(BOOT):raise ValueError('evidence module after startup')
  return html[:start]+block+html[end:]
 return html.replace(BOOT,block+'\n'+BOOT)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 code='\n'.join((ROOT/'web'/n).read_text()for n in ['current_activity_evidence.js','current_activity_evidence_ui.js'])
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(install(a.source.read_text(),code))
