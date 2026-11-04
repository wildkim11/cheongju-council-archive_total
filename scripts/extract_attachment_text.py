"""Offline page-addressed PDF text extraction; never author attribution or semantic approval."""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,re,shutil,subprocess,tempfile,time
from pathlib import Path
from attachment_formats import signature
ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=8*1024*1024
MAX_PAGES=500
MAX_NEW_PDFS=10
def sha(b):return hashlib.sha256(b).hexdigest()
def encoded(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
def write_json(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_bytes(encoded(data));tmp.replace(path)
def tool_version(name):
 if not shutil.which(name):raise RuntimeError('missing offline dependency: '+name)
 r=subprocess.run([name,'-v'],capture_output=True,timeout=10,check=True)
 return (r.stdout+r.stderr).decode('utf-8',errors='replace').splitlines()[0]
def extract_pdf(path):
 info=subprocess.run(['pdfinfo',str(path)],capture_output=True,timeout=30,check=True).stdout.decode('utf-8',errors='strict')
 match=re.search(r'^Pages:\s+(\d+)\s*$',info,re.M)
 if not match or not 0<int(match[1])<=MAX_PAGES:raise ValueError('PDF page limit or page metadata error')
 if re.search(r'^Encrypted:\s+yes',info,re.M):raise ValueError('encrypted PDF is held')
 pages=[];total=0;started=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='council-pdf-text-')as tmp:
  for number in range(1,int(match[1])+1):
   if time.monotonic()-started>120:raise TimeoutError('per-file extraction time limit')
   out=Path(tmp)/'page.txt'
   subprocess.run(['pdftotext','-layout','-enc','UTF-8','-nopgbrk','-f',str(number),'-l',str(number),str(path),str(out)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=30,check=True)
   if out.stat().st_size+total>MAX_BYTES:raise ValueError('extracted text size limit')
   raw=out.read_bytes();text=raw.decode('utf-8',errors='strict');total+=len(raw)
   if '\ufffd'in text or '\x00'in text:raise ValueError('invalid extracted text encoding')
   pages.append({'page':number,'text':text,'text_sha256':sha(raw),'nonspace_characters':len(re.sub(r'\s','',text)),'status':'machine_text_unreviewed'if text.strip()else'needs_ocr_or_visual_review','semantic_verified':False})
 return pages
def verify_document(doc,source_sha):
 if doc.get('schema')!='cheongju-attachment-page-text/1'or doc.get('source_sha256')!=source_sha or doc.get('semantic_verified')is not False or doc.get('member_attribution_allowed')is not False:raise ValueError('attachment text document contract error')
 pages=doc.get('pages')
 if not isinstance(pages,list)or not pages or len(pages)>MAX_PAGES:raise ValueError('attachment text page count error')
 for i,p in enumerate(pages,1):
  if p.get('page')!=i or not isinstance(p.get('text'),str)or sha(p['text'].encode())!=p.get('text_sha256')or p.get('semantic_verified')is not False:raise ValueError('attachment text page integrity error')
  if p.get('nonspace_characters')!=len(re.sub(r'\s','',p['text']))or p.get('status')!=('machine_text_unreviewed'if p['text'].strip()else'needs_ocr_or_visual_review'):raise ValueError('attachment text page status error')
 return doc
def source_refs(root,queue):
 raw=(root/'exports/analyzer/manifest.json').read_bytes();mf=json.loads(raw);refs=collections.defaultdict(list)
 if mf.get('schema')!='cheongju-council-archive-analyzer-export/0.1':raise ValueError('source manifest schema error')
 def strings(obj):
  if isinstance(obj,str):yield obj
  elif isinstance(obj,list):
   for x in obj:yield from strings(x)
  elif isinstance(obj,dict):
   for x in obj.values():yield from strings(x)
 def links(obj):
  if isinstance(obj,list):
   for x in obj:yield from links(x)
  elif isinstance(obj,dict):
   for key,value in obj.items():
    if re.search(r'url|attachment|file|download',key,re.I):yield from strings(value)
    else:yield from links(value)
 for name,m in mf['datasets'].items():
  expected='exports/analyzer/'+name+'.jsonl'
  if not re.fullmatch(r'[a-z_]+',name)or m['path']!=expected:raise ValueError('source dataset path error')
  content=(root/expected).read_bytes()
  if sha(content)!=m['sha256']:raise ValueError('source dataset hash mismatch: '+name)
  rows=content.splitlines()
  if len(rows)!=m['rows']:raise ValueError('source dataset rows mismatch: '+name)
  for i,line in enumerate(rows,1):
   row=json.loads(line)
   for url in set(links(row))&queue.keys():refs[url].append({'dataset':name,'source_row_1based':i,'dataset_sha256':m['sha256'],'source_id':str(row.get('source_id')or row.get('internal_number')or''),'title':row.get('title')or row.get('title_list')or'','official_url':row.get('official_url')or row.get('detail_url')or row.get('source_url')or''})
 return refs,sha(raw)
def stored_path(root,item):
 rel=Path(item.get('path',''))
 if rel.is_absolute()or '..'in rel.parts or rel.parts[:2]!=('archive','attachments'):raise ValueError('unsafe preserved attachment path')
 path=root/rel
 if path.is_symlink()or not path.resolve().is_relative_to((root/'archive/attachments').resolve()):raise ValueError('attachment escapes archive directory')
 raw=path.read_bytes()
 if not 0<len(raw)<=MAX_BYTES or item.get('bytes')!=len(raw)or item.get('sha256')!=sha(raw)or not signature(raw):raise ValueError('preserved attachment hash/size/header mismatch')
 return path,raw
def build(root=ROOT,extractor=None,versions=None,retry_errors=False):
 root=Path(root);out=root/'exports/attachment-text';queue_raw=(root/'reports/automatic/attachments.json').read_bytes();queue=json.loads(queue_raw)
 if not isinstance(queue,dict):raise ValueError('attachment queue schema error')
 from urllib.parse import urlsplit
 for url,item in queue.items():
  u=urlsplit(url)
  if u.scheme!='https'or u.netloc not in {'council.cheongju.go.kr','councilrec.cheongju.go.kr'}or u.fragment or item.get('status')not in {'downloaded','pending','failed','blocked'}:raise ValueError('attachment queue URL/status error')
 refs,mf_sha=source_refs(root,queue);inputs={url:stored_path(root,item)for url,item in queue.items()if item['status']=='downloaded'}
 versions=versions or {'pdfinfo':tool_version('pdfinfo'),'pdftotext':tool_version('pdftotext')};engine={'name':'poppler_pdftotext_layout_utf8_pagewise','versions':versions,'script_sha256':sha(Path(__file__).read_bytes())}
 previous=json.loads((out/'manifest.json').read_text())if(out/'manifest.json').exists()else{};old_files=previous.get('files',{});files={};urls=[];documents={};extractor=extractor or extract_pdf;new_pdfs=0
 for url,item in sorted(queue.items()):
  entry={'url':url,'download_status':item['status'],'source_refs':refs.get(url,[]),'member_attribution_allowed':False,'semantic_verified':False}
  if item['status']!='downloaded':entry['text_status']='not_downloaded';urls.append(entry);continue
  path,raw=inputs[url];digest=item['sha256'];kind=signature(raw);entry['source_sha256']=digest
  if digest not in files:
   meta={'source_sha256':digest,'source_path':item['path'],'source_bytes':len(raw),'container_header':kind,'semantic_verified':False,'member_attribution_allowed':False}
   if kind=='pdf_header':
    old=old_files.get(digest);doc=None
    if old and previous.get('extractor')==engine and old.get('text_status')=='extraction_error'and not retry_errors:
     files[digest]=old;entry['text_status']='extraction_error';urls.append(entry);continue
    if old and previous.get('extractor')==engine and old.get('text_status')in {'machine_text_unreviewed','needs_ocr'}:
     expected=digest+'.json.gz'
     if old.get('file')!=expected:raise ValueError('cached attachment text path error')
     packed=(out/expected).read_bytes()
     if sha(packed)!=old.get('sha256')or len(packed)!=old.get('bytes'):raise ValueError('cached attachment text hash mismatch')
     doc=verify_document(json.loads(gzip.decompress(packed)),digest)
     if doc.get('extractor')!=engine:raise ValueError('cached extractor version mismatch')
    if doc is None and new_pdfs>=MAX_NEW_PDFS:meta['text_status']='processing_pending'
    elif doc is None:
     new_pdfs+=1
     try:doc=verify_document({'schema':'cheongju-attachment-page-text/1','source_sha256':digest,'extractor':engine,'semantic_verified':False,'member_attribution_allowed':False,'pages':extractor(path)},digest)
     except (ValueError,OSError,subprocess.SubprocessError,TimeoutError)as error:meta.update(text_status='extraction_error',error=type(error).__name__+': '+str(error)[:200])
    if doc is not None:
     packed=gzip.compress(encoded(doc),mtime=0);name=digest+'.json.gz';documents[name]=packed
     meta.update(text_status='machine_text_unreviewed'if any(p['nonspace_characters']for p in doc['pages'])else'needs_ocr',file=name,sha256=sha(packed),bytes=len(packed),pages=len(doc['pages']),pages_with_text=sum(p['nonspace_characters']>0 for p in doc['pages']),pages_needing_ocr_or_visual_review=sum(p['nonspace_characters']==0 for p in doc['pages']))
   else:meta['text_status']='needs_ocr'if kind in {'jpeg_header','png_header'}else'unsupported_container'
   files[digest]=meta
  entry['text_status']=files[digest]['text_status'];urls.append(entry)
 counts=dict(collections.Counter(x['text_status']for x in urls));summary={'schema':'cheongju-attachment-text-summary/1','status':'PASS','queued_urls':len(queue),'downloaded_urls':len(inputs),'unique_files':len(files),'text_status_counts':counts,'extracted_pdf_files':sum('file'in x for x in files.values()),'extracted_pdf_pages':sum(x.get('pages',0)for x in files.values()),'pages_with_text':sum(x.get('pages_with_text',0)for x in files.values()),'pages_needing_ocr_or_visual_review':sum(x.get('pages_needing_ocr_or_visual_review',0)for x in files.values()),'human_reviewed_pages':0,'semantic_verified_documents':0,'official_site_requests':0}
 manifest={'schema':'cheongju-attachment-text-release/1','source_queue_sha256':sha(queue_raw),'source_analyzer_manifest_sha256':mf_sha,'extractor':engine,'files':files,'urls':urls,'summary':summary,'all_attachments_processed':False,'member_attribution_allowed':False}
 out.mkdir(parents=True,exist_ok=True)
 for name,content in documents.items():
  temp=out/(name+'.tmp');temp.write_bytes(content);temp.replace(out/name)
 write_json(out/'manifest.json',manifest);write_json(root/'reports/attachment-text-latest.json',summary);return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--retry-errors',action='store_true');a=p.parse_args();print(json.dumps(build(a.root,retry_errors=a.retry_errors),ensure_ascii=False,indent=2))
