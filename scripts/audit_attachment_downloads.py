"""Audit preserved attachment queue and bytes without downloading or parsing content."""
from __future__ import annotations
import argparse,hashlib,json,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HOSTS={'council.cheongju.go.kr','councilrec.cheongju.go.kr'}
def digest(b):return hashlib.sha256(b).hexdigest()
from attachment_formats import signature

def verify_retained_originals(previous_root, candidate_root, candidate_audit):
 previous_path=Path(previous_root)/'reports/automatic/attachments.json'
 if not previous_path.is_file():return 0
 previous=json.loads(previous_path.read_bytes())
 candidate_path=Path(candidate_root)/'reports/automatic/attachments.json'
 candidate=json.loads(candidate_path.read_bytes()) if candidate_path.is_file() else {}
 retained=0
 for url,item in previous.items():
  if item.get('status')!='downloaded':continue
  current=candidate.get(url,{})
  if (current.get('status')!='downloaded'
      or any(current.get(field)!=item.get(field) for field in ('sha256','bytes','path'))
      or item.get('sha256') not in candidate_audit['unique_file_containers']):
   raise ValueError(f'Previously archived attachment missing or changed: {url}')
  retained+=1
 return retained

def build(root=ROOT):
 root=Path(root);path=root/'reports/automatic/attachments.json';counts={'downloaded':0,'failed':0,'pending':0,'blocked':0};verified=0;held=[];unique={};raw=path.read_bytes()if path.exists()else None;queue=json.loads(raw)if raw is not None else{}
 if not isinstance(queue,dict):raise ValueError('attachment queue must be an object')
 for url,item in sorted(queue.items()):
  try:
   u=urllib.parse.urlsplit(url)
   if u.scheme!='https'or u.hostname not in HOSTS or u.netloc!=u.hostname or u.fragment:raise ValueError('unsafe attachment URL')
   if not isinstance(item,dict)or item.get('status')not in counts:raise ValueError('unknown attachment status')
   counts[item['status']]+=1
   if item['status']!='downloaded':continue
   rel=Path(item.get('path',''))
   if rel.is_absolute()or '..'in rel.parts or rel.parts[:2]!=('archive','attachments'):raise ValueError('unsafe attachment storage path')
   content=(root/rel).read_bytes();sha=digest(content);kind=signature(content)
   if sha!=item.get('sha256')or len(content)!=item.get('bytes')or not kind:raise ValueError('attachment hash/size/header mismatch')
   verified+=1;unique[sha]={'bytes':len(content),'container_header':kind,'path':str(rel)}
  except (ValueError,TypeError,OSError)as error:held.append({'url':url,'hold_reason':str(error)})
 result={'schema':'cheongju-attachment-download-audit/1','status':'INTEGRITY_ERROR'if held else'PASS'if raw is not None else'NOT_COLLECTED','queue_present':raw is not None,'source_queue_sha256':digest(raw)if raw is not None else None,'queued_urls':len(queue),'status_counts':counts,'verified_downloaded_urls':verified,'unique_verified_files':len(unique),'unique_verified_bytes':sum(v['bytes']for v in unique.values()),'remaining_unverified_urls':len(queue)-verified,'download_queue_complete':raw is not None and bool(queue)and verified==len(queue)and not held,'held_records':len(held),'held':held,'unique_file_containers':unique,'official_site_requests':0,'image_decoding_verified':False,'document_text_extracted':False,'document_semantics_verified':False,'note':'Checks archived bytes and container headers only. A successful queue snapshot is not full download coverage or document-content validation.'}
 dest=root/'reports/attachment-download-audit.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--strict',action='store_true');a=p.parse_args();r=build(a.root);print(json.dumps({k:v for k,v in r.items()if k not in {'unique_file_containers','held'}},ensure_ascii=False,indent=2));raise SystemExit(1 if a.strict and r['status']=='INTEGRITY_ERROR'else 0)
