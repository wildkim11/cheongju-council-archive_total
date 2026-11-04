(function(root){'use strict';
const raw='https://raw.githubusercontent.com/wildkim11/cheongju-council-archive_total/';
function ok(v,m){if(!v)throw Error(m)}
function official(url){const u=new URL(url);ok(u.protocol==='https:'&&['council.cheongju.go.kr','councilrec.cheongju.go.kr'].includes(u.hostname)&&u.host===u.hostname&&!u.username&&!u.password&&!u.hash,'공식 URL 오류');return url;}
function create(options){
 const cache=new Map(),digest=options.hash||root.CouncilMeetingText.sha,decode=b=>new TextDecoder('utf-8',{fatal:true}).decode(b);
 async function bytes(commit,path,max){ok(/^[a-f0-9]{40}$/.test(commit),'본문 기준 커밋 오류');const key=commit+'/'+path;if(!cache.has(key)){const task=(async()=>{const b=await options.read(raw+key,max);ok(b.byteLength<=max,'활동 자료 크기 제한 초과');return b;})();cache.set(key,task);task.catch(()=>cache.delete(key));}return cache.get(key);}
 async function json(commit,path,max){return JSON.parse(decode(await bytes(commit,path,max)));}
 async function checked(commit,path,meta,max){ok(meta&&/^[a-f0-9]{64}$/.test(meta.sha256),'활동 해시 형식 오류');const b=await bytes(commit,path,max);ok(await digest(b)===meta.sha256,'활동 자료 해시 불일치');if(meta.bytes!==undefined)ok(b.byteLength===meta.bytes,'활동 자료 크기 불일치');return b;}
 async function lines(commit,path,meta,gzip=false){const key=commit+'/'+path+'#lines';if(!cache.has(key)){const task=(async()=>{let b=await checked(commit,path,meta,8*1024*1024);if(gzip){const stream=options.inflate?options.inflate(b):new Blob([b]).stream().pipeThrough(new root.DecompressionStream('gzip'));const r=stream.getReader();let size=0,parts=[];try{while(true){const v=await r.read();if(v.done)break;size+=v.value.byteLength;ok(size<=32*1024*1024,'활동 압축 해제 제한 초과');parts.push(v.value);}b=new Uint8Array(size);let offset=0;for(const p of parts){b.set(p,offset);offset+=p.byteLength;}}finally{await r.cancel().catch(()=>{});r.releaseLock();}}const rows=decode(b).split('\n').filter(x=>x.trim()).map(x=>JSON.parse(x));ok(rows.length===meta.rows,'활동 자료 행수 불일치');return rows;})();cache.set(key,task);task.catch(()=>cache.delete(key));}return cache.get(key);}
 async function load(event,commit,unassigned=false){
  ok(!unassigned||(event.kind==='written_question'&&event.participants[0]?.person_id===null&&event.term===null),'귀속 보류 원자료 범위 오류');
  const datasets={five_minute_speech:'five_minute_speeches',city_question:'city_questions',written_question:'written_questions'},dataset=datasets[event.kind];ok(dataset&&event.source_dataset===dataset&&event.participants.length===1,'활동 본문 연결 대상 오류');const p=event.participants[0];
  const mf=await json(commit,'exports/analyzer/manifest.json',100000);ok(mf.schema==='cheongju-council-archive-analyzer-export/0.1','활동 원장 형식 오류');const meta=mf.datasets[dataset];ok(meta.path==='exports/analyzer/'+dataset+'.jsonl','활동 원장 경로 오류');
  const rows=await lines(commit,meta.path,meta),src=rows[p.source_row_1based-1];ok(src,'활동 원장 행 누락');
  ok(p.activity_id===dataset+':'+src.source_id+':speaker'&&src.date===event.date&&src.speaker_name===p.name&&src.council_scope===event.council_scope&&(src.title||src.title_list)===event.title&&(src.official_url||src.detail_url)===event.official_url,'활동 ID·행·날짜·인물·출처 불일치');official(event.official_url);
  const result={commit,activity_id:p.activity_id,title:event.title,date:event.date,person_id:p.person_id,person_name:p.name,term:event.term,official_url:event.official_url,source_dataset:dataset,source_row_1based:p.source_row_1based,dataset_sha256:meta.sha256,identity_held:unassigned,body_status:'attachment_only',member_text:'',answer_text:'',proofs:[],attachments:[],attachment_status_error:''};
  if(event.kind!=='written_question'){
   const tm=await json(commit,'exports/processing/member_text_inputs_manifest.json',100000),cm=await json(commit,'exports/processing/member_activity_counts_manifest.json',100000);
   ok(tm.schema==='cheongju-member-text-input-release/1'&&cm.schema==='cheongju-member-activity-counts-release/1'&&/^[a-f0-9]{64}$/.test(tm.source_gate_manifest_sha256)&&tm.source_gate_manifest_sha256===cm.gate_manifest_sha256,'본문과 집계 판정 기준 불일치');
   const em=tm.outputs.eligible;ok(em.file==='eligible_member_text_inputs.jsonl.gz','검증 본문 경로 오류');const texts=await lines(commit,'exports/processing/'+em.file,em,true),matches=texts.filter(x=>x.activity_id===p.activity_id);
   ok(matches.length<=1,'의원 본문 검증 근거가 중복됩니다');if(!matches.length){result.body_status='unverified_member_boundary';result.source_body_text=src.body_text||'';}else{const t=matches[0];
   ok(t.text_input_eligible===true&&t.hold_reasons.length===0&&t.person_id===p.person_id&&t.term===event.term&&t.date===event.date&&t.activity_url===event.official_url&&t.source_dataset===dataset&&t.activity_body_sha256===await digest(new TextEncoder().encode(src.body_text||'')),'의원 본문 귀속·게시물 해시 불일치');
   ok(typeof t.member_text==='string'&&await digest(new TextEncoder().encode(t.member_text))===t.member_text_sha256&&t.source_content_proofs.length===1,'의원 본문 해시·근거 오류');
   for(const proof of t.source_content_proofs){official(proof.meeting_url);ok(/^[a-f0-9]{64}$/.test(proof.source_sha256),'회의록 근거 해시 오류');}
   result.member_text=t.member_text;result.member_text_sha256=t.member_text_sha256;result.proofs=t.source_content_proofs;result.body_status='verified_member_text';
   if(event.kind==='city_question'){
    const b=await checked(commit,'exports/processing/question_answer_parts.json',{sha256:tm.source_question_parts_sha256},2*1024*1024),parts=JSON.parse(decode(b));ok(parts.schema==='cheongju-question-answer-parts/1'&&parts.source_dataset_sha256===meta.sha256,'질문·답변 분리 기준 오류');
    const all=parts.rows.filter(x=>x.activity_id===p.activity_id);ok(all.length===1,'질문·답변 분리 ID 중복/누락');const part=all[0];ok(part.question_text_boundary_verified===true&&part.activity_body_sha256===t.activity_body_sha256&&part.candidates.length===1,'질문·답변 경계 미검증');const c=part.candidates[0];
    ok(c.question_text===t.member_text&&c.source_sha256===t.source_content_proofs[0].source_sha256&&c.meeting_id===t.source_content_proofs[0].meeting_id&&await digest(new TextEncoder().encode(c.answer_text))===t.source_content_proofs[0].excluded_answer_sha256,'질문·답변 분리 근거 충돌');result.answer_text=c.answer_text;result.answer_text_sha256=t.source_content_proofs[0].excluded_answer_sha256;
   }
   }
  }
  const urls=[];
  if(event.kind==='written_question')for(const [field,kind]of[['question_file_url','질문'],['answer_file_url','답변']]){const url=official(src[field]),u=new URL(url);ok(u.pathname==='/paper_down.html'&&u.searchParams.get('number')===String(src.source_id)&&u.searchParams.get('gb')===(kind==='질문'?'qna':'ans'),'질문·답변 첨부 ID/역할 불일치');urls.push({url,kind});}
  for(const a of src.attachments||[]){const url=typeof a==='string'?a:a.url||a.href||a.source_url;if(url)urls.push({url:official(url),kind:'게시물 첨부'});}
  result.attachments=[...new Map(urls.map(a=>[a.url,a])).values()].map(a=>({...a,status:'unknown'}));
  if(result.attachments.length){try{const queue=await json(commit,'reports/automatic/attachments.json',2*1024*1024);for(const a of result.attachments){const item=queue[a.url];if(!item){a.status='not_queued';continue;}ok(['downloaded','pending','failed','blocked'].includes(item.status),'첨부 큐 상태 오류');a.status=item.status;if(item.status==='downloaded'){ok(/^[a-f0-9]{64}$/.test(item.sha256)&&Number.isSafeInteger(item.bytes)&&item.bytes>0&&/^archive\/attachments\/[a-zA-Z0-9_./-]+$/.test(item.path)&&!item.path.split('/').includes('..'),'첨부 보존정보 오류');a.sha256=item.sha256;a.bytes=item.bytes;a.archive_url='https://github.com/wildkim11/cheongju-council-archive_total/blob/'+commit+'/'+item.path;}}}catch(e){result.attachment_status_error=e.message;result.attachments=result.attachments.map(({url,kind})=>({url,kind,status:'unknown'}));}}
  return result;
 }
 async function writtenInventory(commit){
  const mf=await json(commit,'exports/analyzer/manifest.json',100000);ok(mf.schema==='cheongju-council-archive-analyzer-export/0.1','활동 원장 형식 오류');const m=mf.datasets.written_questions;ok(m.path==='exports/analyzer/written_questions.jsonl','서면질문 원장 경로 오류');const rows=await lines(commit,m.path,m),ids=new Set();
  return rows.map((s,i)=>{ok(s.source_id&&!ids.has(String(s.source_id)),'서면질문 ID 중복');ids.add(String(s.source_id));return {id:'unassigned|written_questions:'+s.source_id,kind:'written_question',source_dataset:'written_questions',title:s.title,date:s.date,term:null,council_scope:s.council_scope,official_url:official(s.detail_url),participants:[{person_id:null,name:s.speaker_name,role:'speaker',source_row_1based:i+1,activity_id:'written_questions:'+s.source_id+':speaker'}]};});
 }
 return {load,writtenInventory};
}
function text(r){return [r.title,'일자: '+r.date,(r.identity_held?'게시물 표기 인명(개인귀속 보류): '+r.person_name:'의원: '+r.person_name+' · 제'+r.term+'대 · '+r.person_id),'활동 ID: '+r.activity_id,'자료 커밋: '+r.commit,'공식 원문: '+r.official_url,'원장: '+r.source_dataset+' '+r.source_row_1based+'행','원장 SHA-256: '+r.dataset_sha256,'본문 상태: '+r.body_status,'의원 본문 SHA-256: '+(r.member_text_sha256||'미확보'),'','[검증된 의원 발언/질문]',r.member_text||'의원 본문 미검증 — 분석 입력으로 사용하지 않음','','[미분리 게시물 원문 — 의원 본문으로 사용하지 않음]',r.source_body_text||'해당 없음','','[집행부 답변 — 의원 관심 분석에서 제외]',r.answer_text||'이 기록에 분리된 답변 본문 없음',...r.proofs.map(p=>'회의록 근거: '+p.meeting_url+' · '+p.source_sha256),'','[첨부 — 자료 커밋 당시 수집 상태, 파일 본문 미검증]',...r.attachments.map(a=>a.kind+': '+a.url+' · '+a.status+(a.sha256?' · '+a.sha256:'')),r.attachment_status_error?'첨부 상태 확인 실패: '+r.attachment_status_error:''].join('\n');}
const api={create,text};if(typeof module!=='undefined')module.exports=api;root.CouncilActivityContent=api;
})(typeof globalThis!=='undefined'?globalThis:window);
