"""Export an offline user review file from a committed, hash-bound OCR raster snapshot."""
import argparse,base64,gzip,io,json,re,subprocess
from pathlib import Path
import extract_attachment_text as base
import ocr_attachment_pages as ocr
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
def build(root,output,source_commit):
 from PIL import Image
 root=Path(root);output=Path(output)
 if not re.fullmatch('[a-f0-9]{40}',source_commit):raise ValueError('review packet needs a fixed source commit')
 rel='exports/attachment-ocr-review/manifest.json';raw=(root/rel).read_bytes()
 committed=subprocess.check_output(['git','-C',str(root),'show',source_commit+':'+rel])
 if committed!=raw:raise ValueError('review assets are not the selected committed snapshot')
 mf=json.loads(raw)
 if mf.get('schema')!='cheongju-ocr-review-assets/1'or mf.get('analysis_usable')is not False or mf.get('semantic_verified')is not False:raise ValueError('review asset contract error')
 ocr_raw=subprocess.check_output(['git','-C',str(root),'show',source_commit+':exports/attachment-ocr/manifest.json'])
 if base.sha(ocr_raw)!=mf['source_ocr_manifest_sha256']:raise ValueError('review OCR snapshot mismatch')
 ocr_mf=json.loads(ocr_raw);by_key={x['task']['key']:x for x in ocr_mf['items']}
 records=[];seen=set()
 for record in mf['records']:
  r=dict(record);key=r['key'];pixel=r['raster']['pixel_sha256']
  if key in seen or r['image_file']!=pixel+'.png'or r.get('analysis_usable')is not False:raise ValueError('review item ID/path error')
  if not re.fullmatch(r'archive/attachments/[a-f0-9]{64}\.bin',r['task']['source_path']):raise ValueError('review original path error')
  for link in r['task']['source_links']:
   for url in [link['url'],*[ref.get('official_url')for ref in link['source_refs']]]:
    if not url:continue
    u=urlsplit(url)
    if u.scheme!='https'or u.netloc not in {'council.cheongju.go.kr','councilrec.cheongju.go.kr'}or u.fragment:raise ValueError('review official source URL error')
  seen.add(key);image_path=root/'exports/attachment-ocr-review'/r['image_file'];png=image_path.read_bytes()
  item=by_key.get(key)
  if not item or item['sha256']!=r['ocr_document_sha256']or item['task']!=r['task']:raise ValueError('review OCR item provenance mismatch')
  source_doc_raw=subprocess.check_output(['git','-C',str(root),'show',source_commit+':exports/attachment-ocr/'+item['file']])
  if base.sha(source_doc_raw)!=item['sha256']:raise ValueError('review OCR document hash mismatch')
  source_doc=ocr.verify_document(json.loads(gzip.decompress(source_doc_raw)),item['task'],ocr_mf['engine'])
  if source_doc['result']['text']!=r['ocr_text']or source_doc['result']['words']!=r['words']or source_doc['result']['raster']!=r['raster']:raise ValueError('review OCR content mismatch')
  if len(png)>16*1024*1024 or base.sha(png)!=r['image_sha256']:raise ValueError('review raster file hash mismatch')
  if subprocess.check_output(['git','-C',str(root),'show',source_commit+':exports/attachment-ocr-review/'+r['image_file']])!=png:raise ValueError('review raster not committed')
  with Image.open(io.BytesIO(png))as image:
   image.load()
   if image.mode!='L'or image.size!=(r['raster']['width'],r['raster']['height'])or base.sha(image.tobytes())!=pixel:raise ValueError('review raster pixel mismatch')
  if base.sha(r['ocr_text'].encode())!=r['ocr_text_sha256']:raise ValueError('review OCR text hash mismatch')
  r['source_commit']=source_commit;r['image_uri']='data:image/png;base64,'+base64.b64encode(png).decode();r['title']=next((ref['title']for link in r['task']['source_links']for ref in link['source_refs']if ref.get('title')),'보존 첨부 '+key[:10]);records.append(r)
 packet={'schema':'cheongju-ocr-review-packet/1','source_commit':source_commit,'assets_manifest_sha256':base.sha(raw),'source_ocr_manifest_sha256':mf['source_ocr_manifest_sha256'],'engine':mf['engine'],'records':records,'human_reviewed_pages':0,'semantic_verified':False,'analysis_usable':False}
 data=json.dumps(packet,ensure_ascii=False,sort_keys=True,separators=(',',':')).replace('<','\\u003c');digest=base.sha(data.encode());template=(root/'web/ocr_review.html').read_text();core=(root/'web/ocr_review_core.js').read_text()
 for marker in ['__OCR_PACKET__','__OCR_PACKET_SHA__','__OCR_CORE__']:
  if template.count(marker)!=1:raise ValueError('ambiguous OCR review template marker')
 if '</script'in core.lower():raise ValueError('unsafe review core script')
 replacements={'__OCR_PACKET__':data,'__OCR_PACKET_SHA__':digest,'__OCR_CORE__':core}
 html=re.sub('__OCR_PACKET__|__OCR_PACKET_SHA__|__OCR_CORE__',lambda m:replacements[m[0]],template);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(html)
 return {'schema':'cheongju-ocr-review-packet-summary/1','status':'PASS','records':len(records),'source_commit':source_commit,'packet_sha256':digest,'bytes':output.stat().st_size,'human_reviewed_pages':0,'analysis_usable':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--output',type=Path,required=True);p.add_argument('--source-commit',required=True);a=p.parse_args();print(json.dumps(build(a.root,a.output,a.source_commit),ensure_ascii=False,indent=2))
