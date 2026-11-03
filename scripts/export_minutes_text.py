"""Hash-verified, reproducible compressed plain-text meeting packs for consumers.

Runs in the GitHub collection candidate. No HTML/UI is produced. Official URLs,
source IDs, original Markdown hashes and normalized text hashes stay attached.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,shutil,tempfile
from pathlib import Path
from audit_stage_c import markdown_parts,canon
ROOT=Path(__file__).resolve().parents[1]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def export(root=ROOT):
 root=Path(root);index=root/'indexes/integrated/meetings.json';raw_index=index.read_bytes();rows=json.loads(raw_index);seen=set();catalog={'schema':'cheongju-meeting-text-packs/1','source_index_sha256':sha(raw_index),'rows':len(rows),'parts':[]}
 with tempfile.TemporaryDirectory(prefix='meeting-text-packs-') as td:
  tmp=Path(td);counts={};handles={};streams={};total_text=0
  try:
   for row in sorted(rows,key=lambda r:(r['term'],r['date'],r['meeting_id'])):
    mid=row['meeting_id']
    if mid in seen:raise ValueError('duplicate meeting ID')
    seen.add(mid);rel=Path(row['path'])
    if rel.is_absolute() or '..' in rel.parts or rel.parts[:2]!=('archive','meetings'):raise ValueError('unsafe meeting path')
    raw=(root/rel).read_bytes()
    if sha(raw)!=row['sha256']:raise ValueError('meeting original hash mismatch: '+mid)
    title,metadata,body=markdown_parts(raw.decode('utf-8'));text_hash=sha(canon(body).encode())
    if text_hash!=row['content_sha256']:raise ValueError('meeting body hash mismatch: '+mid)
    term=row['term'];name=f'term-{term}.jsonl.gz'
    if term not in streams:
     handles[term]=(tmp/name).open('wb');streams[term]=gzip.GzipFile(filename='',mode='wb',fileobj=handles[term],mtime=0);counts[term]=0
    record={k:row[k] for k in ('meeting_id','term','date','official_url','publication_status')};record.update(title=title,text=body,source_sha256=row['sha256'],content_sha256=text_hash)
    encoded=(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n').encode();streams[term].write(encoded);counts[term]+=1;total_text+=len(body.encode())
  finally:
   for s in streams.values():s.close()
   for h in handles.values():h.close()
  for term in sorted(counts):
   p=tmp/f'term-{term}.jsonl.gz';raw=p.read_bytes();catalog['parts'].append({'term':term,'file':p.name,'rows':counts[term],'bytes':len(raw),'sha256':sha(raw)})
  catalog['text_bytes']=total_text;catalog['compressed_bytes']=sum(p['bytes'] for p in catalog['parts']);out=root/'exports/minutes-text';out.mkdir(parents=True,exist_ok=True)
  for part in catalog['parts']:shutil.copyfile(tmp/part['file'],out/part['file'])
  (out/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return catalog
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(export(a.root),ensure_ascii=False,indent=2))
