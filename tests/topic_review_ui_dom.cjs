// Usage: node tests/topic_review_ui_dom.cjs /absolute/path/to/jsdom
(async()=>{
const {JSDOM}=require(process.argv[2]),fs=require('fs'),assert=require('assert');
const html=fs.readFileSync(require('path').join(__dirname,'../exports/topic-review/review.html'),'utf8');
const downloads=[];
const dom=new JSDOM(html,{runScripts:'dangerously',url:'https://local.invalid/review',beforeParse(w){w.URL.createObjectURL=b=>{downloads.push(b);return 'blob:test';};w.URL.revokeObjectURL=()=>{};w.HTMLAnchorElement.prototype.click=function(){};}});
const w=dom.window,$=id=>w.document.getElementById(id),ev=id=>$(id).dispatchEvent(new w.Event('input',{bubbles:true}));
const packet=JSON.parse($('payload').textContent),draft=packet.drafts[packet.tasks[0].case_id];
assert.equal($('cases').options.length,40);assert.equal(w.document.querySelectorAll('[data-topic]').length,18);assert.equal($('ai').hidden,true);assert.equal($('source').value,packet.tasks[0].member_text);
$('complete').click();assert.match($('status').textContent,/식별자/);
$('reviewer').value='synthetic-test-reviewer';ev('reviewer');$('decision').value=draft.decision;ev('decision');
for(const id of draft.topic_ids){const n=w.document.querySelector(`[data-topic="${id}"]`);n.checked=true;n.dispatchEvent(new w.Event('change'));const e=draft.evidence_spans.find(e=>e.topic_id===id);$('source').setSelectionRange(Array.from($('source').value).slice(0,e.start).join('').length,Array.from($('source').value).slice(0,e.end).join('').length);$('evidenceTopic').value=id;$('addEvidence').click();}
$('rationale').value='테스트 전용 판단';ev('rationale');$('reason').value='테스트 전용 경계 구분';ev('reason');$('fullRead').checked=true;ev('fullRead');$('complete').click();assert.match($('progress').textContent,/완료 1/);$('export').click();assert.equal(downloads.length,1);const exported=await new Promise((resolve,reject)=>{const r=new w.FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsText(downloads[0]);});const submitted=JSON.parse(exported.trim());assert.equal(submitted.review_origin,'human');assert.equal(submitted.review_method,'independent');assert.equal(submitted.case_id,packet.tasks[0].case_id);assert.equal(submitted.evaluation_reference_eligible,false);
let state=JSON.parse(w.localStorage.getItem(w.localStorage.key(0)));assert.equal(state.entries[packet.tasks[0].case_id].completed,true);assert.equal(state.entries[packet.tasks[0].case_id].revealed,false);
$('reveal').click();assert.equal($('ai').hidden,false);assert.match($('method').textContent,/AI 참고/);assert.match($('progress').textContent,/완료 0/);$('complete').click();$('next').click();$('prev').click();assert.equal($('ai').hidden,false);$('rationale').value+='수정';ev('rationale');assert.match($('progress').textContent,/완료 0/);$('export').click();assert.equal(downloads.length,1);$('backup').click();assert.equal(downloads.length,2);
const backupState=JSON.parse(w.localStorage.getItem(w.localStorage.key(0)));backupState.entries[packet.tasks[0].case_id].revealed=false;backupState.entries[packet.tasks[0].case_id].completed=true;
Object.defineProperty($('restore'),'files',{configurable:true,value:[{text:async()=>JSON.stringify(backupState)}]});await $('restore').onchange();assert.equal($('ai').hidden,false);assert.match($('progress').textContent,/완료 0/);
backupState.snapshot='stale';Object.defineProperty($('restore'),'files',{configurable:true,value:[{text:async()=>JSON.stringify(backupState)}]});await $('restore').onchange();assert.match($('status').textContent,/맞지 않거나/);
// Selection offsets must be Python Unicode code points, even after an astral character.
w.eval("P.tasks[0].member_text='😀교육정책';render();");$('source').setSelectionRange(2,4);$('evidenceTopic').value=draft.topic_ids[0];$('addEvidence').click();state=JSON.parse(w.localStorage.getItem(w.localStorage.key(0)));const last=state.entries[packet.tasks[0].case_id].evidence_spans.at(-1);assert.equal(last.start,1);assert.equal(last.end,3);assert.equal(last.quote,'교육');
// Stored inputs use textContent; markup in review text never runs.
w.eval("P.tasks[0].person_name='<img src=x onerror=alert(1)>';render();");assert.equal($('title').querySelector('img'),null);
console.log(JSON.stringify({cases:40,topics:18,blind_default:true,validation:true,completion_export:true,edit_invalidates_completion:true,reveal_persists:true,unicode_offsets:true,text_injection_safe:true,backup_restore:true,stale_backup_rejected:true,actual_human_reviews_created:0}));dom.window.close();

})().catch(e=>{console.error(e);process.exitCode=1;});
