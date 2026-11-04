"""Build exact-pixel review rasters; abort rather than display misaligned OCR boxes."""
import argparse,gzip,io,json,subprocess,tempfile,warnings
from pathlib import Path
import extract_attachment_text as base
import ocr_attachment_pages as ocr
ROOT=Path(__file__).resolve().parents[1]
def raster_image(path,kind,page):
 from PIL import Image,ImageOps
 with tempfile.TemporaryDirectory(prefix='council-review-raster-')as temp:
  input_path=path
  if kind=='pdf_header':
   prefix=Path(temp)/'page'
   subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-r',str(ocr.SETTINGS['pdf_dpi']),'-scale-to',str(ocr.SETTINGS['max_raster_side']),'-singlefile','-png',str(path),str(prefix)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=45,check=True);input_path=Path(temp)/'page.png'
  try:
   with warnings.catch_warnings():
    warnings.simplefilter('error',Image.DecompressionBombWarning)
    with Image.open(input_path)as image:
     if image.width*image.height>40_000_000:raise ValueError('review image pixel limit')
     image.load();gray=ImageOps.exif_transpose(image).convert('L');gray.thumbnail((3000,3000),Image.Resampling.LANCZOS);gray=ImageOps.autocontrast(gray)
  except (Image.DecompressionBombWarning,Image.DecompressionBombError)as e:raise ValueError('review image pixel limit')from e
  return gray
def png_bytes(image,expected):
 if image.mode!='L'or image.size!=(expected['width'],expected['height'])or base.sha(image.tobytes())!=expected['pixel_sha256']:raise ValueError('review raster pixels differ from OCR coordinates')
 out=io.BytesIO();image.save(out,format='PNG',compress_level=6);return out.getvalue()
def build(root=ROOT,renderer=raster_image):
 root=Path(root);out=root/'exports/attachment-ocr-review';raw=(root/'exports/attachment-ocr/manifest.json').read_bytes();mf=json.loads(raw);text_raw=(root/'exports/attachment-text/manifest.json').read_bytes();text=json.loads(text_raw)
 if mf.get('schema')!='cheongju-attachment-ocr-release/1'or mf.get('analysis_usable')is not False or base.sha(text_raw)!=mf['source_attachment_text_manifest_sha256']:raise ValueError('OCR review input snapshot mismatch')
 queue=json.loads((root/'reports/automatic/attachments.json').read_text());stored={i['sha256']:base.stored_path(root,i)for i in queue.values()if i['status']=='downloaded'};records=[];images={};seen=set();held=[]
 for item in mf['items']:
  if item['status']not in {'machine_ocr_unreviewed','ocr_no_text_unreviewed'}:held.append({'key':item['task']['key'],'status':item['status']});continue
  task=item['task'];key=task['key'];sha=task['source_sha256']
  if key in seen or item['file']!=key+'.json.gz':raise ValueError('duplicate/unsafe OCR review item')
  seen.add(key);packed=(root/'exports/attachment-ocr'/item['file']).read_bytes()
  if len(packed)!=item['bytes']or base.sha(packed)!=item['sha256']:raise ValueError('OCR review document hash mismatch')
  doc=ocr.verify_document(json.loads(gzip.decompress(packed)),task,mf['engine']);path,original=stored[sha]
  if str(path.relative_to(root))!=task['source_path']or base.signature(original)!=task['source_kind']or sha!=text['files'][sha]['source_sha256']:raise ValueError('OCR review original mismatch')
  image=renderer(path,task['source_kind'],task['page']);png=png_bytes(image,doc['result']['raster']);pixel=doc['result']['raster']['pixel_sha256'];name=pixel+'.png';images[name]=png
  records.append({'key':key,'task':task,'ocr_document_sha256':item['sha256'],'ocr_text':doc['result']['text'],'ocr_text_sha256':doc['result']['text_sha256'],'raster':doc['result']['raster'],'image_file':name,'image_sha256':base.sha(png),'words':doc['result']['words'],'semantic_verified':False,'member_attribution_allowed':False,'analysis_usable':False})
 out.mkdir(parents=True,exist_ok=True)
 for name,png in images.items():
  temp=out/(name+'.tmp');temp.write_bytes(png);temp.replace(out/name)
 result={'schema':'cheongju-ocr-review-assets/1','source_ocr_manifest_sha256':base.sha(raw),'engine':mf['engine'],'records':records,'held':held,'human_reviewed_pages':0,'semantic_verified':False,'analysis_usable':False};base.write_json(out/'manifest.json',result)
 summary={'schema':'cheongju-ocr-review-assets-summary/1','status':'PASS','ready_items':len(records),'held_items':len(held),'unique_rasters':len(images),'raster_bytes':sum(map(len,images.values())),'human_reviewed_pages':0,'analysis_usable':False,'official_site_requests':0};base.write_json(root/'reports/ocr-review-assets-latest.json',summary);return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(build(a.root),ensure_ascii=False,indent=2))
