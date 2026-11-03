(function(root){'use strict';
const LIMIT=120*1024*1024, LINE=8*1024*1024;
function ok(v,m){if(!v)throw Error(m)}
function canon(s){return s.replace(/[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/gu,' ').replace(/^ | $/g,'')}
async function sha(bytes){ok(root.crypto&&root.crypto.subtle,'현재 브라우저에서 SHA-256 검증을 사용할 수 없습니다');return Array.from(new Uint8Array(await root.crypto.subtle.digest('SHA-256',bytes)),x=>x.toString(16).padStart(2,'0')).join('')}
async function readPack(bytes,part,expected,options={}){
 const digest=options.hash||sha;
 ok(bytes.byteLength===part.bytes&&part.bytes<=32*1024*1024,'본문 묶음 크기 불일치');
 ok(await digest(bytes)===part.sha256,'본문 묶음 SHA-256 불일치');
 ok(expected&&expected.term===part.term,'선택 회의록과 묶음 대수가 다릅니다');
 let stream;if(options.inflate)stream=options.inflate(bytes);else{ok(typeof root.DecompressionStream==='function','압축 해제를 지원하는 최신 브라우저에서 여세요');stream=new Blob([bytes]).stream().pipeThrough(new root.DecompressionStream('gzip'));}
 const reader=stream.getReader(),decoder=new TextDecoder('utf-8',{fatal:true});let buffer='',expanded=0,count=0,found=null;const seen=new Set();
 function line(s){if(!s.trim())return;ok(s.length<=LINE,'회의록 한 건의 크기 제한 초과');const x=JSON.parse(s);ok(typeof x.meeting_id==='string'&&!seen.has(x.meeting_id),'회의록 ID 누락 또는 중복');seen.add(x.meeting_id);ok(x.term===part.term,'묶음 내부 대수 불일치');count++;if(x.meeting_id===expected.meeting_id){for(const k of ['term','date','official_url','source_sha256','content_sha256'])ok(x[k]===expected[k],'선택 회의록 출처 불일치: '+k);ok(typeof x.text==='string','본문 형식 오류');found=x;}}
 try{while(true){const {value,done}=await reader.read();if(done)break;expanded+=value.byteLength;ok(expanded<=LIMIT,'압축 해제 크기 제한 초과');buffer+=decoder.decode(value,{stream:true});let pos;while((pos=buffer.indexOf('\n'))>=0){line(buffer.slice(0,pos));buffer=buffer.slice(pos+1)}ok(buffer.length<=LINE,'회의록 한 건의 크기 제한 초과');}buffer+=decoder.decode();if(buffer)line(buffer);ok(count===part.rows,'본문 묶음 행수 불일치');ok(found,'선택 회의록이 묶음에 없습니다');ok(await digest(new TextEncoder().encode(canon(found.text)))===found.content_sha256,'회의록 본문 해시 불일치');return found;}finally{await reader.cancel().catch(()=>{});reader.releaseLock();}
}
function text(record){return [record.title,'일자: '+record.date,'회의록 ID: '+record.meeting_id,'공식 원문: '+record.official_url,'원본 SHA-256: '+record.source_sha256,'본문 SHA-256: '+record.content_sha256,'','[보존 본문]',record.text].join('\n')}
const api={readPack,sha,text,canon};if(typeof module!=='undefined')module.exports=api;root.CouncilMeetingText=api;
})(typeof globalThis!=='undefined'?globalThis:window);
