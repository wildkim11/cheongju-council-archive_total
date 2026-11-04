const fs=require('fs'),path=require('path'),zlib=require('zlib'),assert=require('assert'),crypto=require('crypto'),api=require('../web/attachment_text_reader.js');
const root=path.resolve(__dirname,'..'),hash=b=>crypto.createHash('sha256').update(b).digest('hex'),commit='a'.repeat(40),file='exports/attachment-text/manifest.json';
function fixture(mutate=()=>{}){const changes=new Map(),m=JSON.parse(fs.readFileSync(path.join(root,file)));mutate(m,changes);const b=Buffer.from(JSON.stringify(m));changes.set(file,b);const config={schema:'cheongju-attachment-view/1',commit,manifest_sha256:hash(b)},reader=api.create({hash:async b=>hash(b),read:async url=>{const p=url.split('/'+commit+'/')[1];assert(p,'Unexpected fixture URL');return changes.has(p)?changes.get(p):fs.readFileSync(path.join(root,p));}});return {m,config,reader,changes};}
async function run(){
 let f=fixture(),m=await f.reader.manifest(f.config),pages=0;const sha=Object.keys(m.files).find(k=>m.files[k].file);for(const [key,meta]of Object.entries(m.files))if(meta.file){const d=await f.reader.document(f.config,m,key);pages+=d.pages.length;const txt=api.text(f.config,m,key,d,1);assert(txt.includes(m.urls.find(u=>u.source_sha256===key).url));assert(txt.includes(d.pages[0].text_sha256));}assert.equal(pages,m.summary.extracted_pdf_pages);
 await assert.rejects(f.reader.prepare(f.config,m,commit,{status:'behind'}),/이전/);
 f=fixture(m=>{m.urls.pop();});await assert.rejects(f.reader.manifest(f.config),/요약/);
 f=fixture(m=>{const r=m.urls.find(u=>u.source_refs.length).source_refs[0];r.source_row_1based=99999999;});await assert.rejects(f.reader.manifest(f.config),/좌표/);
 f=fixture(m=>{m.files[sha].source_path='../../other.pdf';});await assert.rejects(f.reader.manifest(f.config),/근거/);
 f=fixture();m=await f.reader.manifest(f.config);f.changes.set('exports/attachment-text/'+m.files[sha].file,Buffer.from('altered'));await assert.rejects(f.reader.document(f.config,m,sha),/묶음 해시/);
 for(const change of [d=>{d.pages[0].text+='tamper';},d=>{d.pages[0].page=99;},d=>{d.semantic_verified=true;}]){f=fixture((m,changes)=>{const meta=m.files[sha],p='exports/attachment-text/'+meta.file,d=JSON.parse(zlib.gunzipSync(fs.readFileSync(path.join(root,p))));change(d);const b=zlib.gzipSync(JSON.stringify(d));changes.set(p,b);meta.bytes=b.length;meta.sha256=hash(b);});m=await f.reader.manifest(f.config);await assert.rejects(f.reader.document(f.config,m,sha),/오류/);}
 f=fixture();m=await f.reader.manifest(f.config);f.changes.set(m.files[sha].source_path,Buffer.from('%PDF wrong'));await assert.rejects(f.reader.original(f.config,m,sha),/원본 해시/);
 console.log('10 attachment-reader integrity checks passed; '+pages+' pages verified');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
