const assert=require('assert'),api=require('../web/current_activity_evidence.js'),counts=require('../web/member_activity_counts_updates.js');
function fixture(){
 const profile=(id,name,term=4)=>({key:`cheongju_integrated|${term}|${id}`,person_id:id,name,term,council_scope:'cheongju_integrated',eligible:[],held:[],held_rows:0});
 const a=profile('a','가의원'),b=profile('b','나의원'),c=profile('c','다의원',3);
 const row=(p,n,role,line)=>({activity_id:`bill:${p.term}:${n}:${p.person_id}:${role}`,analysis_gate:{base_count_eligible:true},date:'2026-01-01',kind:'bill',official_url:`https://councilrec.cheongju.go.kr/content/minutes/iframe_bill_view1.html?number=${n}&daesu=${p.term}`,role,source_dataset:'bill_proposers_member_only',source_row_1based:line,term:p.term,title:'의안 '+n});
 a.eligible=[row(a,1,'representative',1),row(a,2,'co_proposer',3)];b.eligible=[row(b,1,'co_proposer',2)];c.eligible=[row(c,1,'representative',4)];
 const held=row(b,2,'co_proposer',5);held.analysis_gate={base_count_eligible:false,hold_reasons:['dated_tenure_conflict']};b.held=[held];b.held_rows=1;
 for(const p of[a,b,c])p.counts=counts.summary(p.eligible);
 return {schema:'cheongju-member-activity-counts/1',source_commit:'a'.repeat(40),artifact_sha256:'b'.repeat(64),profiles:[a,b,c],source_rows:5,eligible_rows:4,held_rows:1,unassigned_held_rows:0};
}
const tests={
 'held participation cannot create a shared edge'(){const p=api.project(fixture());assert.equal(p.events.length,3);const rows=api.shared(p.events,'a',{kind:'master'}).rows;assert.equal(rows.length,1);assert.equal(rows[0].event_ids.length,1);assert.equal(rows[0].person_id,'b');},
 'same number in another term remains a separate event'(){const p=api.project(fixture());assert.equal(p.events.filter(e=>e.id.endsWith(':1')).length,2);assert.equal(api.select(p,{person_id:'c',term:'제4대'}).length,0);},
 'conflicting source metadata fails closed'(){const x=fixture();x.profiles[1].eligible[0].date='2026-01-02';assert.throws(()=>api.project(x),/메타데이터/);},
 'invalid official URL fails closed'(){const x=fixture();x.profiles[0].eligible[0].official_url='https://attacker.invalid/x';assert.throws(()=>api.project(x),/URL/);},
 'false eligibility cannot enter the projection'(){const x=fixture();x.profiles[0].eligible[0].analysis_gate.base_count_eligible=false;assert.throws(()=>api.project(x),/보류/);},
 'compact null gates expand without changing the source'(){const x=counts.compact(fixture()),before=JSON.stringify(x),p=api.project(x);assert.equal(p.events.length,3);assert.equal(JSON.stringify(x),before);},
 'member audience cannot calculate peer counts even with supplied rows'(){const p=api.project(fixture());const s=api.shared(p.events,'a',{kind:'member'});assert.equal(s.available,false);assert.equal(s.rows.length,0);},
 'year query and exact profile ID filters intersect'(){const p=api.project(fixture());assert.equal(api.select(p,{person_id:'a',year:'2026',query:'의안 1'}).length,1);assert.equal(api.select(p,{person_id:'a',year:'2025'}).length,0);},
 'duplicate event participation is rejected'(){const x=fixture();x.profiles[0].eligible.push({...x.profiles[0].eligible[0]});assert.throws(()=>api.project(x),/중복/);},
 'roles and raw evidence coordinates are retained'(){const e=api.project(fixture()).events.find(e=>e.term===4&&e.id.endsWith(':1'));assert.deepEqual(e.participants.map(p=>[p.role,p.source_row_1based]),[['representative',1],['co_proposer',2]]);}
};
for(const [name,fn] of Object.entries(tests)){fn();console.log('PASS '+name);}console.log(Object.keys(tests).length+' evidence checks passed');
