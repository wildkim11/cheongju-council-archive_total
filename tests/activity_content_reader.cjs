const assert=require('assert'),crypto=require('crypto'),zlib=require('zlib'),api=require('../web/activity_content_reader.js');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex'),enc=x=>Buffer.from(JSON.stringify(x)),commit='a'.repeat(40);
function fixture(change=()=>{}){
 const src={source_id:'7',title:'시험 발언',date:'2026-01-01',speaker_name:'가의원',council_scope:'cheongju_integrated',official_url:'https://council.cheongju.go.kr/content/activity/fiveRemark.html?number=7',body_text:'검증 본문',attachments:[]};
 const t={activity_id:'five_minute_speeches:7:speaker',text_input_eligible:true,hold_reasons:[],person_id:'p',term:4,date:src.date,activity_url:src.official_url,source_dataset:'five_minute_speeches',activity_body_sha256:hash(Buffer.from(src.body_text)),member_text:src.body_text,member_text_sha256:hash(Buffer.from(src.body_text)),source_content_proofs:[{meeting_url:'https://councilrec.cheongju.go.kr/minutes/svc/web/cms/mnts/SvcMntsViewer.php?schSn=1',source_sha256:'b'.repeat(64)}]};
 const event={kind:'five_minute_speech',source_dataset:'five_minute_speeches',title:src.title,date:src.date,term:4,council_scope:src.council_scope,official_url:src.official_url,participants:[{person_id:'p',name:src.speaker_name,activity_id:t.activity_id,source_row_1based:1}]};
 const texts=[t];change({src,t,event,texts});const data=Buffer.from(JSON.stringify(src)+'\n'),pack=zlib.gzipSync(texts.map(x=>JSON.stringify(x)).join('\n'));
 const files={'exports/analyzer/five_minute_speeches.jsonl':data,'exports/analyzer/manifest.json':enc({schema:'cheongju-council-archive-analyzer-export/0.1',datasets:{five_minute_speeches:{path:'exports/analyzer/five_minute_speeches.jsonl',rows:1,sha256:hash(data)}}}),'exports/processing/member_text_inputs_manifest.json':enc({schema:'cheongju-member-text-input-release/1',source_gate_manifest_sha256:'c'.repeat(64),outputs:{eligible:{file:'eligible_member_text_inputs.jsonl.gz',rows:texts.length,bytes:pack.length,sha256:hash(pack)}}}),'exports/processing/member_activity_counts_manifest.json':enc({schema:'cheongju-member-activity-counts-release/1',gate_manifest_sha256:'c'.repeat(64)}),'exports/processing/eligible_member_text_inputs.jsonl.gz':pack};
 const reader=api.create({hash:async b=>hash(b),read:async url=>{const p=url.split('/'+commit+'/')[1];if(!files[p])throw Error('Missing '+p);return files[p];}});return {reader,event,files};
}
async function run(){
 let f=fixture(),r=await f.reader.load(f.event,commit);assert.equal(r.member_text,'검증 본문');assert(api.text(r).includes(f.event.official_url));
 f=fixture();f.files['exports/analyzer/five_minute_speeches.jsonl']=Buffer.from('tampered');await assert.rejects(f.reader.load(f.event,commit),/해시/);
 f=fixture(({t})=>{t.person_id='other-person';});await assert.rejects(f.reader.load(f.event,commit),/귀속/);
 f=fixture(({t})=>{t.text_input_eligible=false;});await assert.rejects(f.reader.load(f.event,commit),/귀속/);
 f=fixture(({src})=>{src.source_id='999';});await assert.rejects(f.reader.load(f.event,commit),/불일치/);
 f=fixture(({texts})=>texts.length=0);r=await f.reader.load(f.event,commit);assert.equal(r.body_status,'unverified_member_boundary');assert.equal(r.member_text,'');assert.equal(r.source_body_text,'검증 본문');
 f=fixture(({t})=>{t.member_text='변조';});await assert.rejects(f.reader.load(f.event,commit),/본문 해시/);
 f=fixture(({src})=>{src.attachments=['https://attacker.invalid/file.pdf'];});await assert.rejects(f.reader.load(f.event,commit),/URL/);
 f=fixture(({src})=>{src.attachments=['https://council.cheongju.go.kr/down.php?x=1'];});r=await f.reader.load(f.event,commit);assert.equal(r.attachments[0].status,'unknown');assert(r.attachment_status_error);assert(api.text(r).includes('https://council.cheongju.go.kr/down.php?x=1'));
 console.log('9 activity-content checks passed');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
