"""Validate user-entered transcription records against a fixed Git snapshot, without approval."""
from __future__ import annotations
import argparse,base64,collections,datetime,gzip,hashlib,io,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import ocr_attachment_pages as ocr
HEX=re.compile('[a-f0-9]{64}');COMMIT=re.compile('[a-f0-9]{40}')
FIELDS={'schema','record_kind','source_commit','source_links','packet_sha256','key','source_sha256','raster_pixel_sha256','ocr_document_sha256','status','corrected_text','note','reviewer','source_checked','analysis_usable','semantic_verified','updated_at'}
def digest(raw):return hashlib.sha256(raw).hexdigest()
def require(value,message):
 if not value:raise ValueError(message)
def git_bytes(root,commit,path):
 require(COMMIT.fullmatch(commit),'invalid source commit')
 return subprocess.check_output(['git','-C',str(root),'show',commit+':'+path],stderr=subprocess.PIPE)
def load_packet(path,root,current_commit=None):
 raw=Path(path).read_bytes();require(len(raw)<=80*1024*1024,'packet exceeds size limit');html=raw.decode('utf-8-sig')
 tags=re.findall(r'<script id="packet" type="application/json">(.*?)</script>',html,re.S);hashes=re.findall(r"expected='([a-f0-9]{64})';let records=packet\.records",html)
 require(len(tags)==len(hashes)==1,'missing or ambiguous review packet')
 packet_sha=hashes[0];require(digest(tags[0].encode())==packet_sha,'packet content hash mismatch');p=json.loads(tags[0])
 require(p.get('schema')=='cheongju-ocr-review-packet/1'and p.get('analysis_usable')is False and p.get('semantic_verified')is False and p.get('human_reviewed_pages')==0,'invalid packet approval flags')
 commit=p.get('source_commit','');asset_raw=git_bytes(root,commit,'exports/attachment-ocr-review/manifest.json');assets=json.loads(asset_raw)
 require(digest(asset_raw)==p.get('assets_manifest_sha256')and assets.get('schema')=='cheongju-ocr-review-assets/1'and assets.get('analysis_usable')is False and assets.get('semantic_verified')is False,'packet source assets mismatch')
 ocr_raw=git_bytes(root,commit,'exports/attachment-ocr/manifest.json');require(digest(ocr_raw)==p.get('source_ocr_manifest_sha256')==assets.get('source_ocr_manifest_sha256'),'packet OCR snapshot mismatch')
 ocr_mf=json.loads(ocr_raw);require(ocr_mf.get('schema')=='cheongju-attachment-ocr-release/1'and ocr_mf.get('analysis_usable')is False and ocr_mf.get('semantic_verified')is False and ocr_mf.get('engine')==assets.get('engine'),'packet OCR source contract mismatch');ocr_by={x['task']['key']:x for x in ocr_mf['items']}
 require(p.get('engine')==assets.get('engine'),'packet OCR engine mismatch');rows=p.get('records');require(isinstance(rows,list)and 0<len(rows)<=1000,'invalid packet records')
 source_rows=assets['records'];by={r['key']:r for r in source_rows}
 require(len(by)==len(source_rows),'duplicate source record')
 if 'record_start' in p:
  start=p['record_start']
  require(type(start) is int and 0<=start<=len(source_rows)-len(rows),'invalid packet part range')
  require([r.get('key') for r in rows]==[r['key'] for r in source_rows[start:start+len(rows)]],'packet part source order mismatch')
 else:require(len(by)==len(rows),'packet source record count mismatch')
 seen=set()
 for r in rows:
  key=r.get('key');require(key in by and key not in seen,'unknown/duplicate packet record');seen.add(key);a=by[key]
  require(all(r.get(k)==v for k,v in a.items())and r.get('source_commit')==commit,'packet record/source proof mismatch')
  item=ocr_by.get(key);require(item is not None and item['sha256']==r['ocr_document_sha256']and item['task']==r['task']and re.fullmatch('[a-f0-9]{64}-p[1-9][0-9]*\\.json\\.gz',item['file']),'packet OCR document reference mismatch')
  packed=git_bytes(root,commit,'exports/attachment-ocr/'+item['file']);require(len(packed)<=8*1024*1024 and digest(packed)==item['sha256'],'packet OCR document hash mismatch')
  with gzip.GzipFile(fileobj=io.BytesIO(packed))as stream:document_raw=stream.read(16*1024*1024+1)
  require(len(document_raw)<=16*1024*1024,'packet OCR document size limit');doc=ocr.verify_document(json.loads(document_raw),item['task'],ocr_mf['engine']);require(all(r[k]==doc['result'][v]for k,v in [('ocr_text','text'),('ocr_text_sha256','text_sha256'),('words','words'),('raster','raster')]),'packet OCR content mismatch')
  uri=r.get('image_uri','');require(uri.startswith('data:image/png;base64,'),'invalid packet image URI');image=base64.b64decode(uri.split(',',1)[1],validate=True)
  require(len(image)<=16*1024*1024 and image.startswith(b'\x89PNG\r\n\x1a\n')and digest(image)==a['image_sha256'],'packet image hash mismatch')
  require(digest(r['ocr_text'].encode())==r['ocr_text_sha256'],'packet OCR text hash mismatch')
 if current_commit is None:current_commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
 current=json.loads(git_bytes(root,current_commit,'exports/attachment-ocr-review/manifest.json'));current_by={r['key']:r for r in current['records']}
 return {'packet_sha256':packet_sha,'source_commit':commit,'current_commit':current_commit,'assets_manifest_sha256':digest(asset_raw),'records':{r['key']:r for r in rows},'current_records':current_by}
def parse_rows(path,packet_sha,max_rows):
 raw=Path(path).read_bytes();require(len(raw)<=40*1024*1024,'review file exceeds size limit');text=raw.decode('utf-8-sig').strip();require(text,'empty review file')
 try:obj=json.loads(text)
 except json.JSONDecodeError:obj=None
 if isinstance(obj,dict)and obj.get('schema')=='cheongju-ocr-review-backup/1':
  require(obj.get('packet_sha256')==packet_sha,'backup packet mismatch');rows=obj.get('records')
 elif isinstance(obj,dict):rows=[obj]
 elif obj is not None:raise ValueError('expected JSONL records or review backup')
 else:rows=[json.loads(line)for line in text.splitlines()if line.strip()]
 require(isinstance(rows,list)and 0<len(rows)<=max_rows,'invalid review row count');require(all(isinstance(x,dict)for x in rows),'non-object review row');return rows
def validate_row(x,snapshot):
 require(set(x)==FIELDS,'unknown or missing review fields');require(x['schema']=='cheongju-ocr-transcription-review/1'and x['record_kind']=='user_entered_transcription_review_not_gold','unsupported review schema/kind')
 r=snapshot['records'].get(x['key']);require(r is not None,'unknown review record ID');current=snapshot['current_records'].get(x['key'])
 require(current is not None and all(current.get(k)==r.get(k)for k in ['task','ocr_document_sha256','ocr_text_sha256','raster']),'stale current source proofs — hold for comparison')
 require(x['packet_sha256']==snapshot['packet_sha256']and x['source_commit']==snapshot['source_commit']and x['source_sha256']==r['task']['source_sha256']and x['raster_pixel_sha256']==r['raster']['pixel_sha256']and x['ocr_document_sha256']==r['ocr_document_sha256']and x['source_links']==r['task']['source_links'],'review source/version proof mismatch')
 require(x['analysis_usable']is False and x['semantic_verified']is False,'review cannot grant analysis or semantic approval');require(type(x['source_checked'])is bool,'invalid source-check flag')
 for key,limit in [('corrected_text',1000000),('note',10000),('reviewer',200)]:require(isinstance(x[key],str)and len(x[key])<=limit and '\x00'not in x[key],key+' format/size error')
 status=x['status'];require(status in {'unreviewed','draft','checked_transcription','held'},'invalid review status')
 stamp=x['updated_at']
 if stamp is not None:
  require(isinstance(stamp,str)and len(stamp)<=64,'invalid review timestamp');parsed=datetime.datetime.fromisoformat(stamp.replace('Z','+00:00'));require(parsed.tzinfo is not None,'review timestamp needs timezone')
 if status=='checked_transcription':require(x['reviewer'].strip()and x['source_checked']and x['corrected_text'].strip()and stamp is not None,'checked transcription needs reviewer, source check, text and timestamp')
 if status=='held':require(x['reviewer'].strip()and x['note'].strip()and stamp is not None,'held review needs reviewer, reason and timestamp')
 if status=='unreviewed':require(x['corrected_text']==r['ocr_text']and not x['source_checked']and not x['reviewer']and not x['note']and stamp is None,'unreviewed row contains undeclared edits')
 return dict(x)
def intake(packet_path,reviews_path=None,root=ROOT,current_commit=None):
 report={'schema':'cheongju-ocr-review-intake/1','status':'NO_USER_INPUT','input_records':0,'validated_records':[],'held':[],'declared_status_counts':{},'declared_checked_transcriptions':0,'analysis_usable_records':0,'semantic_approved_records':0,'reviewer_identity_authenticated':False,'review_actions_independently_verified':False,'official_site_requests':0}
 try:snapshot=load_packet(packet_path,root,current_commit)
 except (ValueError,KeyError,TypeError,OSError,EOFError,subprocess.SubprocessError)as error:report.update(status='HELD_INVALID_PACKET',held=[{'reason':str(error)}]);return report
 report['source_snapshot']={k:snapshot[k]for k in ['packet_sha256','source_commit','current_commit','assets_manifest_sha256']}
 if reviews_path is None:return report
 try:
  rows=parse_rows(reviews_path,snapshot['packet_sha256'],len(snapshot['records']));report['input_records']=len(rows);seen=set();validated=[]
  for number,row in enumerate(rows,1):
   try:
    require(row.get('key')not in seen,'duplicate review record ID');seen.add(row.get('key'));validated.append(validate_row(row,snapshot))
   except (ValueError,TypeError,KeyError)as error:report['held'].append({'input_row_1based':number,'key':row.get('key')if isinstance(row.get('key'),str)else None,'reason':str(error)})
  if report['held']:report['status']='HELD_INVALID_INPUT';return report
  counts=dict(collections.Counter(x['status']for x in validated));report.update(status='VALIDATED_NOT_APPROVED',validated_records=validated,declared_status_counts=counts,declared_checked_transcriptions=counts.get('checked_transcription',0));return report
 except (ValueError,TypeError,KeyError,OSError)as error:report.update(status='HELD_INVALID_INPUT',held=[{'reason':str(error)}]);return report
def save_report(report,path):
 require(report['status']in {'NO_USER_INPUT','VALIDATED_NOT_APPROVED'},'held input is not written over an existing report')
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n');temp.replace(p)
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--packet',type=Path,required=True);parser.add_argument('--reviews',type=Path);parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--output',type=Path);args=parser.parse_args();result=intake(args.packet,args.reviews,args.root)
 if args.output and result['status']in {'NO_USER_INPUT','VALIDATED_NOT_APPROVED'}:save_report(result,args.output)
 print(json.dumps({k:v for k,v in result.items()if k!='validated_records'},ensure_ascii=False,indent=2));raise SystemExit(2 if result['status'].startswith('HELD_')else 0)
