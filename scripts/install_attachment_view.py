"""Install a separate-version attachment viewer without modifying prior data payloads."""
import argparse,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
START='// BEGIN COUNCIL_ATTACHMENT_VIEW'
END='// END COUNCIL_ATTACHMENT_VIEW'
BOOT='readStore();render();window.councilBootReady();'
TAG=re.compile(r'<script id="attachment-text-view" type="application/json">.*?</script>',re.S)
def install(html,code,descriptor):
 if html.count(BOOT)!=1 or 'window.__activityContent='not in html:raise ValueError('unknown Stage47 activity template')
 if '</script'in code.lower():raise ValueError('unsafe script terminator')
 if descriptor.get('schema')!='cheongju-attachment-view/1'or not re.fullmatch('[a-f0-9]{40}',descriptor.get('commit',''))or not re.fullmatch('[a-f0-9]{64}',descriptor.get('manifest_sha256','')):raise ValueError('invalid attachment descriptor')
 tag='<script id="attachment-text-view" type="application/json">'+json.dumps(descriptor,separators=(',',':'))+'</script>'
 matches=list(TAG.finditer(html))
 if matches:
  if len(matches)!=1:raise ValueError('duplicate attachment descriptor')
  m=matches[0];html=html[:m.start()]+tag+html[m.end():]
 else:
  anchor='<script id="release-bundle" type="application/json">'
  if html.count(anchor)!=1 or 'id="attachment-text-view"'in html:raise ValueError('ambiguous attachment descriptor location')
  html=html.replace(anchor,tag+anchor)
 block=START+'\n'+code.rstrip()+'\n'+END
 if START in html or END in html:
  if html.count(START)!=1 or html.count(END)!=1 or html.index(START)>html.index(END):raise ValueError('ambiguous attachment viewer markers')
  start=html.index(START);end=html.index(END)+len(END)
  if end>html.index(BOOT):raise ValueError('attachment viewer after startup')
  return html[:start]+block+html[end:]
 return html.replace(BOOT,block+'\n'+BOOT)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--descriptor',type=Path,required=True);a=p.parse_args()
 code='\n'.join((ROOT/'web'/n).read_text()for n in ['attachment_text_reader.js','attachment_text_ui.js'])
 result=install(a.source.read_text(),code,json.loads(a.descriptor.read_text()));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(result)
