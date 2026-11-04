"""Offline Korean OCR for preserved images and empty PDF text pages; never promote attribution."""
from __future__ import annotations
import argparse,csv,gzip,io,json,math,os,re,shutil,subprocess,tempfile,warnings
from pathlib import Path
import extract_attachment_text as base
ROOT=Path(__file__).resolve().parents[1]
MAX_NEW=24
SETTINGS={'language':'kor+eng','psm':11,'oem':1,'pdf_dpi':200,'max_raster_side':3000}
def environment(tessdata_dir=None):
 from PIL import __version__
 if not shutil.which('tesseract'):raise RuntimeError('Korean OCR requires tesseract')
 command=['tesseract','--list-langs']
 if tessdata_dir:command+=['--tessdata-dir',str(tessdata_dir)]
 r=subprocess.run(command,capture_output=True,text=True,check=True,timeout=10);text=r.stdout+r.stderr
 if not tessdata_dir:
  match=re.search(r'"([^"]+)"',text)
  if not match:raise RuntimeError('cannot resolve OCR model directory')
  tessdata_dir=Path(match[1])
 tessdata_dir=Path(tessdata_dir);models={}
 for language in ['kor','eng']:
  p=tessdata_dir/(language+'.traineddata')
  if not p.is_file():raise RuntimeError('required OCR language is unavailable: '+language)
  models[language]=base.sha(p.read_bytes())
 version=subprocess.run(['tesseract','--version'],capture_output=True,text=True,check=True,timeout=10).stdout.splitlines()[0]
 engine={'name':'tesseract_sparse_korean_english','tesseract_version':version,'poppler_version':base.tool_version('pdftoppm'),'pillow_version':__version__,'language_model_sha256':models,'settings':SETTINGS,'script_sha256':base.sha(Path(__file__).read_bytes())}
 return engine,tessdata_dir
def validate_result(result):
 raster=result.get('raster',{});w=raster.get('width');h=raster.get('height')
 if not isinstance(w,int)or not isinstance(h,int)or not 0<w<=3000 or not 0<h<=3000 or raster.get('mode')!='L'or not re.fullmatch('[a-f0-9]{64}',raster.get('pixel_sha256','')):raise ValueError('OCR raster contract error')
 text=result.get('text')
 if not isinstance(text,str)or len(text.encode())>1024*1024 or '\ufffd'in text or '\x00'in text or base.sha(text.encode())!=result.get('text_sha256'):raise ValueError('OCR text hash/encoding error')
 words=result.get('words')
 if not isinstance(words,list)or len(words)>100000:raise ValueError('OCR word count error')
 for word in words:
  if not isinstance(word.get('text'),str)or not word['text'].strip():raise ValueError('OCR empty word error')
  box=word.get('box')
  if not isinstance(box,list)or len(box)!=4 or any(type(n)is not int for n in box)or box[0]<0 or box[1]<0 or box[2]<=0 or box[3]<=0 or box[0]+box[2]>w or box[1]+box[3]>h:raise ValueError('OCR word coordinate error')
  conf=word.get('tesseract_confidence')
  if not isinstance(conf,(int,float))or not math.isfinite(conf)or not 0<=conf<=100:raise ValueError('OCR confidence range error')
 return result
def recognize(path,kind,page,tessdata_dir):
 from PIL import Image,ImageOps
 with tempfile.TemporaryDirectory(prefix='council-ocr-')as temp:
  folder=Path(temp);input_path=path
  if kind=='pdf_header':
   prefix=folder/'render'
   subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-r',str(SETTINGS['pdf_dpi']),'-scale-to',str(SETTINGS['max_raster_side']),'-singlefile','-png',str(path),str(prefix)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=45,check=True)
   input_path=folder/'render.png'
  try:
   with warnings.catch_warnings():
    warnings.simplefilter('error',Image.DecompressionBombWarning)
    with Image.open(input_path)as image:
     if image.width*image.height>40_000_000:raise ValueError('OCR image pixel limit')
     image.load();gray=ImageOps.exif_transpose(image).convert('L');gray.thumbnail((3000,3000),Image.Resampling.LANCZOS);gray=ImageOps.autocontrast(gray)
  except (Image.DecompressionBombWarning,Image.DecompressionBombError)as error:raise ValueError('OCR image pixel limit')from error
  raster={'width':gray.width,'height':gray.height,'mode':'L','pixel_sha256':base.sha(gray.tobytes())};prepared=folder/'input.png';gray.save(prepared)
  output=folder/'ocr'
  subprocess.run(['tesseract',str(prepared),str(output),'--tessdata-dir',str(tessdata_dir),'-l',SETTINGS['language'],'--psm',str(SETTINGS['psm']),'--oem',str(SETTINGS['oem']),'-c','tessedit_create_txt=1','-c','tessedit_create_tsv=1'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=60,check=True,env={**os.environ,'OMP_THREAD_LIMIT':'1'})
  if output.with_suffix('.txt').stat().st_size>1024*1024 or output.with_suffix('.tsv').stat().st_size>8*1024*1024:raise ValueError('OCR output size limit')
  text=output.with_suffix('.txt').read_text(encoding='utf-8');words=[]
  for row in csv.DictReader(io.StringIO(output.with_suffix('.tsv').read_text(encoding='utf-8')),delimiter='\t',quoting=csv.QUOTE_NONE):
   if row['level']=='5'and(row.get('text')or'').strip():words.append({'text':row['text'],'box':[int(row[n])for n in ['left','top','width','height']],'tesseract_confidence':float(row['conf'])})
  return validate_result({'raster':raster,'text':text,'text_sha256':base.sha(text.encode()),'words':words})
def inputs(root):
 manifest_raw=(root/'exports/attachment-text/manifest.json').read_bytes();m=json.loads(manifest_raw);queue_raw=(root/'reports/automatic/attachments.json').read_bytes();queue=json.loads(queue_raw)
 if m.get('schema')!='cheongju-attachment-text-release/1'or base.sha(queue_raw)!=m.get('source_queue_sha256'):raise ValueError('OCR queue snapshot mismatch')
 refs,source_sha=base.source_refs(root,queue)
 if source_sha!=m.get('source_analyzer_manifest_sha256'):raise ValueError('OCR source manifest snapshot mismatch')
 stored={item['sha256']:base.stored_path(root,item)for item in queue.values()if item['status']=='downloaded'}
 if set(stored)!=set(m['files']):raise ValueError('OCR preserved file set mismatch')
 tasks=[]
 for sha,f in sorted(m['files'].items()):
  path,raw=stored[sha];kind=base.signature(raw)
  if f.get('source_sha256')!=sha or f.get('source_path')!=str(path.relative_to(root))or f.get('source_bytes')!=len(raw)or f.get('container_header')!=kind:raise ValueError('OCR original descriptor mismatch')
  pages=[];origin_hash=None
  if kind in {'jpeg_header','png_header'}:pages=[1]
  elif kind=='pdf_header'and f.get('file'):
   if f['file']!=sha+'.json.gz':raise ValueError('OCR input page path error')
   packed=(root/'exports/attachment-text'/f['file']).read_bytes()
   if len(packed)!=f['bytes']or base.sha(packed)!=f['sha256']:raise ValueError('OCR input page pack hash error')
   d=base.verify_document(json.loads(gzip.decompress(packed)),sha)
   if d['extractor']!=m['extractor']or len(d['pages'])!=f['pages']:raise ValueError('OCR input extractor/page mismatch')
   pages=[p['page']for p in d['pages']if p['nonspace_characters']==0];origin_hash=f['sha256']
  for page in pages:
   key=sha+'-p'+str(page);links=[{'url':u['url'],'source_refs':refs.get(u['url'],[])}for u in m['urls']if u.get('source_sha256')==sha]
   tasks.append({'key':key,'source_sha256':sha,'source_path':f['source_path'],'source_kind':kind,'page':page,'page_coordinate':'pdf_1based'if kind=='pdf_header'else'single_image_1','input_text_document_sha256':origin_hash,'source_links':links})
 return manifest_raw,tasks
def verify_document(doc,task,engine):
 if doc.get('schema')!='cheongju-attachment-page-ocr/1'or doc.get('task')!=task or doc.get('engine')!=engine or doc.get('semantic_verified')is not False or doc.get('member_attribution_allowed')is not False or doc.get('analysis_usable')is not False:raise ValueError('OCR document provenance error')
 validate_result(doc['result']);expected='machine_ocr_unreviewed'if doc['result']['text'].strip()else'ocr_no_text_unreviewed'
 if doc.get('status')!=expected:raise ValueError('OCR document status error')
 return doc
def build(root=ROOT,tessdata_dir=None,engine=None,recognizer=None,retry_errors=False):
 root=Path(root);input_raw,tasks=inputs(root)
 if engine is None:engine,tessdata_dir=environment(tessdata_dir)
 recognizer=recognizer or(lambda path,kind,page:recognize(path,kind,page,tessdata_dir));out=root/'exports/attachment-ocr';previous=json.loads((out/'manifest.json').read_text())if(out/'manifest.json').exists()else{};old={x['task']['key']:x for x in previous.get('items',[])};items=[];outputs={};processed=0
 for task in tasks:
  key=task['key'];cached=old.get(key);item={'task':task,'status':'ocr_pending','semantic_verified':False,'member_attribution_allowed':False}
  same_input=cached and all(cached['task'].get(k)==task.get(k)for k in ['source_sha256','source_kind','page','page_coordinate'])
  if previous.get('engine')==engine and same_input:
   if cached['status']in {'machine_ocr_unreviewed','ocr_no_text_unreviewed'}:
    if cached.get('file')!=key+'.json.gz':raise ValueError('OCR cache path error')
    raw=(out/cached['file']).read_bytes()
    if len(raw)!=cached['bytes']or base.sha(raw)!=cached['sha256']:raise ValueError('OCR cache integrity error')
    cached_doc=verify_document(json.loads(gzip.decompress(raw)),cached['task'],engine)
    if cached['task']!=task:
     cached_doc['task']=task;raw=gzip.compress(base.encoded(verify_document(cached_doc,task,engine)),mtime=0);outputs[cached['file']]=raw;cached={**cached,'task':task,'bytes':len(raw),'sha256':base.sha(raw)}
    items.append(cached);continue
   if cached['status']=='ocr_error_held'and not retry_errors:items.append({**cached,'task':task});continue
  if processed>=MAX_NEW:items.append(item);continue
  processed+=1
  try:
   result=validate_result(recognizer(root/task['source_path'],task['source_kind'],task['page']));doc=verify_document({'schema':'cheongju-attachment-page-ocr/1','task':task,'engine':engine,'result':result,'status':'machine_ocr_unreviewed'if result['text'].strip()else'ocr_no_text_unreviewed','semantic_verified':False,'member_attribution_allowed':False,'analysis_usable':False},task,engine)
   raw=gzip.compress(base.encoded(doc),mtime=0);name=key+'.json.gz';outputs[name]=raw;item.update(status=doc['status'],file=name,bytes=len(raw),sha256=base.sha(raw),words=len(result['words']),text_sha256=result['text_sha256'])
  except (ValueError,OSError,subprocess.SubprocessError,RuntimeError)as e:item.update(status='ocr_error_held',error=type(e).__name__+': '+str(e)[:200])
  items.append(item)
 counts={s:sum(i['status']==s for i in items)for s in ['machine_ocr_unreviewed','ocr_no_text_unreviewed','ocr_error_held','ocr_pending']};summary={'schema':'cheongju-attachment-ocr-summary/1','status':'PASS','target_pages':len(tasks),'image_pages':sum(t['source_kind']!='pdf_header'for t in tasks),'pdf_pages':sum(t['source_kind']=='pdf_header'for t in tasks),'status_counts':counts,'human_reviewed_pages':0,'semantic_verified_pages':0,'official_site_requests':0,'confidence_is_accuracy':False}
 out.mkdir(parents=True,exist_ok=True)
 for name,raw in outputs.items():
  temp=out/(name+'.tmp');temp.write_bytes(raw);temp.replace(out/name)
 base.write_json(out/'manifest.json',{'schema':'cheongju-attachment-ocr-release/1','source_attachment_text_manifest_sha256':base.sha(input_raw),'engine':engine,'items':items,'summary':summary,'member_attribution_allowed':False,'semantic_verified':False,'analysis_usable':False});base.write_json(root/'reports/attachment-ocr-latest.json',summary);return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--tessdata-dir',type=Path);p.add_argument('--retry-errors',action='store_true');a=p.parse_args();print(json.dumps(build(a.root,a.tessdata_dir,retry_errors=a.retry_errors),ensure_ascii=False,indent=2))
