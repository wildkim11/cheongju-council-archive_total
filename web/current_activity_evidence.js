// A read-only projection of the validated count ledger, never of legacy candidates.
(function(root){'use strict';
function project(input){
 const api=root.CouncilCountsUpdates||(typeof require==='function'?require('./member_activity_counts_updates.js'):null);
 const d=api.expand(input);api.validate(d);
 const events=new Map();
 for(const p of d.profiles)for(const r of p.eligible){
  const parts=r.activity_id.split(':');
  if(r.kind==='bill'&&parts[0]!=='bill')throw Error('의안 사건 ID 접두사 오류');
  const id=p.council_scope+'|'+(r.kind==='bill'?parts.slice(0,3).join(':'):r.source_dataset+':'+r.source_row_1based);
  const meta={id,council_scope:p.council_scope,term:p.term,kind:r.kind,title:r.title,date:r.date,official_url:r.official_url,source_dataset:r.source_dataset};
  let e=events.get(id);
  if(e&&JSON.stringify(e.meta)!==JSON.stringify(meta))throw Error('공동사건 메타데이터 충돌');
  if(!e){e={...meta,meta,participants:[]};events.set(id,e);}
  if(e.participants.some(x=>x.person_id===p.person_id))throw Error('동일 인물·사건 중복');
  e.participants.push({person_id:p.person_id,name:p.name,role:r.role,source_row_1based:r.source_row_1based,activity_id:r.activity_id});
 }
 return {source_commit:input.source_commit,artifact_sha256:input.artifact_sha256,eligible_rows:d.eligible_rows,held_rows:d.held_rows,profiles:d.profiles.map(p=>({key:p.key,person_id:p.person_id,name:p.name,term:p.term,council_scope:p.council_scope})),events:[...events.values()].map(({meta,...e})=>e).sort((a,b)=>b.date.localeCompare(a.date)||a.id.localeCompare(b.id))};
}
function select(data,{person_id='',term='전체 대수',year='전체 기간',query='',kind='bill'}={}){
 return data.events.filter(e=>e.kind===kind&&(!person_id||e.participants.some(p=>p.person_id===person_id))&&(term==='전체 대수'||term===`제${e.term}대`)&&(year==='전체 기간'||e.date.startsWith(year))&&(!query||[e.title,e.id,...e.participants.map(p=>p.name)].join(' ').includes(query)));
}
function shared(events,person_id,audience){
 if(audience.kind!=='master')return {available:false,reason:'개인판에는 다른 의원의 최신 참여행이 포함되지 않아 공동참여 비교를 계산하지 않습니다.',rows:[]};
 if(!person_id)return {available:false,reason:'의원을 선택하면 같은 대수의 공동참여 의안을 확인할 수 있습니다.',rows:[]};
 const peers=new Map();
 for(const e of events){
  if(e.kind!=='bill'||!e.participants.some(p=>p.person_id===person_id))continue;
  for(const p of e.participants)if(p.person_id!==person_id){
   const key=e.council_scope+'|'+e.term+'|'+p.person_id;
   const row=peers.get(key)||{key,person_id:p.person_id,name:p.name,term:e.term,council_scope:e.council_scope,event_ids:[]};
   if(!row.event_ids.includes(e.id))row.event_ids.push(e.id);
   peers.set(key,row);
  }
 }
 return {available:true,rows:[...peers.values()].sort((a,b)=>a.term-b.term||a.name.localeCompare(b.name,'ko')||a.key.localeCompare(b.key))};
}
const api={project,select,shared};if(typeof module!=='undefined')module.exports=api;root.CouncilCurrentActivity=api;
})(typeof globalThis!=='undefined'?globalThis:window);
