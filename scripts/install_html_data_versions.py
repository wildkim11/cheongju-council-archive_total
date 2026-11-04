"""Install a bounded Stage47 data-version UI extension without rewriting data payloads."""
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
START='// BEGIN COUNCIL_DATA_VERSIONS_UI'
END='// END COUNCIL_DATA_VERSIONS_UI'
BOOT='readStore();render();window.councilBootReady();'
def install(html,code):
 block=START+'\n'+code.rstrip()+'\n'+END+'\n'
 if START in html or END in html:
  if html.count(START)!=1 or html.count(END)!=1 or html.index(START)>html.index(END):raise ValueError('ambiguous data-version extension markers')
  start=html.index(START);end=html.index(END)+len(END)
  return html[:start]+block.rstrip('\n')+html[end:]
 if html.count(BOOT)!=1 or 'function dataVersionsPanel()'in html:raise ValueError('unknown or ambiguous Stage47 startup template')
 return html.replace(BOOT,block+BOOT)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();text=install(a.source.read_text(),(ROOT/'web/data_versions_ui.js').read_text());a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(text)
