"""Independently verify written-question file links against preserved detail HTML."""
from __future__ import annotations
import argparse,gzip,hashlib,json,urllib.parse
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Anchors(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.hrefs=[]
 def handle_starttag(self,tag,attrs):
  if tag.lower()=='a':
   values=[v for k,v in attrs if k.lower()=='href']
   if len(values)==1 and values[0]:self.hrefs.append(values[0])
def digest(raw):return hashlib.sha256(raw).hexdigest()
def number(url):
 if not isinstance(url,str):return None
 q=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query,keep_blank_values=True)
 return q.get('number')
def valid_download(url,sid,kind):
 if not isinstance(url,str):return False
 u=urllib.parse.urlsplit(url);q=urllib.parse.parse_qs(u.query,keep_blank_values=True)
 return u.scheme=='https'and u.hostname=='council.cheongju.go.kr'and u.netloc=='council.cheongju.go.kr'and u.path=='/paper_down.html'and not u.fragment and q.get('number')==[sid]and q.get('gb')==[kind]
def audit_row(row,html,page_url):
 sid=row.get('source_id')
 if not isinstance(sid,str)or not sid.isdigit()or number(page_url)!=[sid]:raise ValueError('detail page/source ID mismatch')
 parser=Anchors();parser.feed(html);links={urllib.parse.urljoin(page_url,u)for u in parser.hrefs}
 result={}
 for field,kind in [('question_file_url','qna'),('answer_file_url','ans')]:
  observed={u for u in links if valid_download(u,sid,kind)};saved=row.get(field)
  if not saved or not valid_download(saved,sid,kind):raise ValueError(field+': wrong record/type/host or missing link')
  if observed!={saved}:raise ValueError(field+': link absent or ambiguous in preserved detail HTML')
  result[field]=saved
 return result

def build(root=ROOT):
 root=Path(root);src=root/'archive/activities/written_questions.json';raw=src.read_bytes();rows=json.loads(raw);manifests=[]
 for path in (root/'archive/source_responses/manifests').glob('*.json'):
  m=json.loads(path.read_text())
  if m.get('schema')=='cheongju-source-responses/1'and m.get('family')=='activities':manifests.append((m.get('collection_started_at',''),path,m))
 chosen=max(manifests,key=lambda t:(t[0],str(t[1])))if manifests else None;proofs={};results=[]
 if chosen:
  for r in chosen[2].get('responses',[]):proofs.setdefault(r['url'],{})[(r['path'],r['decoded_utf8_sha256'])]=r
 seen=set()
 for row in rows:
  out={'source_id':row.get('source_id'),'detail_url':row.get('detail_url'),'status':'held'}
  try:
   if row.get('source_id')in seen:raise ValueError('duplicate source ID')
   seen.add(row.get('source_id'));options=list(proofs.get(row.get('detail_url'),{}).values())
   if len(options)!=1:raise ValueError('missing or conflicting preserved detail response')
   proof=options[0];rel=Path(proof['path'])
   if rel.is_absolute()or '..'in rel.parts or rel.parts[:2]!=('archive','source_responses'):raise ValueError('unsafe response path')
   body=gzip.decompress((root/rel).read_bytes())
   if digest(body)!=proof['decoded_utf8_sha256']or len(body)!=proof['bytes']:raise ValueError('response hash/size mismatch')
   links=audit_row(row,body.decode('utf-8'),row['detail_url']);out.update(status='verified',**links,source_response_path=str(rel),source_response_sha256=digest(body))
  except (ValueError,TypeError,KeyError,OSError,EOFError)as error:out['hold_reason']=str(error)
  results.append(out)
 report={'schema':'cheongju-written-question-link-audit/1','status':'PASS'if rows and all(r['status']=='verified'for r in results)else'HOLD','source_records':len(rows),'verified_records':sum(r['status']=='verified'for r in results),'held_records':sum(r['status']!='verified'for r in results),'source_dataset_sha256':digest(raw),'source_manifest':str(chosen[1].relative_to(root))if chosen else None,'source_manifest_sha256':digest(chosen[1].read_bytes())if chosen else None,'collection_started_at':chosen[0]if chosen else None,'rows':results,'official_site_requests':0,'attachment_contents_verified':False,'identity_promotions':0,'date_changes':0}
 dest=root/'reports/written-question-link-audit.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--strict',action='store_true');a=p.parse_args();r=build(a.root);print(json.dumps({k:v for k,v in r.items()if k!='rows'},ensure_ascii=False,indent=2));raise SystemExit(1 if a.strict and r['status']!='PASS'else 0)
