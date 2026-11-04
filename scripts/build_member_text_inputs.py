"""Gate member text inputs by both existing attribution and source-verified content."""
from __future__ import annotations
import argparse,collections,gzip,json
from pathlib import Path
from process_meeting_segments import sha,load_export,encoded,pack,write_json
from resolve_activity_spacing_matches import match
from build_question_answer_parts import split_candidate
ROOT=Path(__file__).resolve().parents[1]
def reasons_for(gate,proof_count):
 reasons=list(gate['hold_reasons'])
 if gate['base_count_eligible']!= (not reasons):raise ValueError('contradictory count gate')
 if proof_count==0:reasons.append('member_text_boundary_unverified')
 elif proof_count!=1:reasons.append('ambiguous_member_text_source')
 return sorted(set(reasons))
def build(root=ROOT):
 root=Path(root);out=root/'exports/processing';pm=json.loads((out/'manifest.json').read_text());gm=json.loads((out/'analysis_activity_gate_manifest.json').read_text());mf=json.loads((root/'exports/analyzer/manifest.json').read_text());parts=json.loads((out/'question_answer_parts.json').read_text());data={n:load_export(root,n,mf)for n in ['five_minute_speeches','city_questions']}
 if parts['schema']!='cheongju-question-answer-parts/1'or parts['source_dataset_sha256']!=mf['datasets']['city_questions']['sha256']:raise ValueError('text input question split snapshot mismatch')
 roles=[]
 for label in ['eligible','held']:
  meta=gm['outputs'][label];raw=(out/meta['file']).read_bytes()
  if sha(raw)!=meta['sha256']:raise ValueError('text input gate hash mismatch')
  batch=[json.loads(l)for l in gzip.decompress(raw).splitlines()]
  if len(batch)!=meta['rows']:raise ValueError('text input gate row mismatch')
  if any(r['analysis_gate']['base_count_eligible']!=(label=='eligible')for r in batch):raise ValueError('text input gate partition mismatch')
  roles.extend(batch)
 if len({r['activity_id']for r in roles})!=len(roles):raise ValueError('duplicate activity gate ID')
 role_raw=(out/'activity_roles.jsonl.gz').read_bytes()
 if sha(role_raw)!=pm['activity_roles']['sha256']or sha(role_raw)!=gm['input_activity_roles_sha256']:raise ValueError('text input role snapshot mismatch')
 idxraw=(root/'indexes/integrated/meetings.json').read_bytes();catraw=(out/'meeting_segments_catalog.json').read_bytes()
 if sha(idxraw)!=pm['source_index_sha256']or sha(catraw)!=pm['meeting_catalog']['sha256']or parts['source_index_sha256']!=sha(idxraw):raise ValueError('text input source snapshot mismatch')
 sources={m['meeting_id']:m for m in json.loads(idxraw)};partby={p['activity_id']:p for p in parts['rows']}
 if len(partby)!=len(parts['rows']):raise ValueError('duplicate question split ID')
 targets=collections.defaultdict(list);proofs=collections.defaultdict(list);lookup={}
 for r in roles:
  if r['source_dataset']not in data:continue
  src=data[r['source_dataset']][r['source_row_1based']-1];aid=f"{r['source_dataset']}:{src['source_id']}:speaker"
  if aid!=r['activity_id']or src['date']!=r['date']or src['speaker_name']!=r['person_name']:raise ValueError('text input source/role mismatch')
  lookup[aid]=(r,src);targets[r['date']].append(aid)
 for e in json.loads(catraw):
  m=sources[e['meeting_id']]
  if m['date']not in targets:continue
  source=(root/m['path']).read_bytes();packed=(out/e['path']).read_bytes()
  if sha(source)!=m['sha256']or sha(packed)!=e['sha256']:raise ValueError('text input source/shard hash mismatch')
  doc=json.loads(gzip.decompress(packed));text=source.decode();segments={s['segment_id']:s for s in doc['segments']}
  if doc['source_sha256']!=m['sha256']or doc['date']!=m['date']or doc['term']!=m['term']:raise ValueError('text input meeting context mismatch')
  for aid in targets[m['date']]:
   role,src=lookup[aid];body=src.get('body_text')or''
   if src['council_scope']!=m['council_scope']:continue
   part=partby.get(aid)
   if part and part['question_text_boundary_verified']:
    if len(part['candidates'])!=1 or part['activity_body_sha256']!=sha(body.encode()):raise ValueError('text input altered split evidence')
    c=part['candidates'][0]
    if c['meeting_id']!=m['meeting_id']:continue
    q=segments.get(c['question_segment_id']);a=segments.get(c['answer_segment_id'])
    if not q or not a or q.get('speaker_name')!=role['person_name']or not q.get('speaker_category','').startswith('council_')or not q.get('person_id')or a.get('speaker_category')!='executive_or_staff'or a['content_start']<=q['char_end']:raise ValueError('text input split speaker mismatch')
    result=split_candidate(body,text[q['content_start']:q['char_end']],text[a['content_start']:a['char_end']])
    if not result or result['question_text']!=c['question_text']or result['answer_text']!=c['answer_text']or c['source_sha256']!=m['sha256']:raise ValueError('text input split no longer reproduces')
    if role.get('person_id')and (q['person_id']!=role['person_id']or m['term']!=role['term']):continue
    proofs[aid].append({'text':result['question_text'],'method':'verified_question_prefix_and_executive_tail','meeting_id':m['meeting_id'],'segment_id':q['segment_id'],'source_sha256':m['sha256'],'meeting_url':m['official_url'],'excluded_answer_sha256':sha(result['answer_text'].encode())})
    continue
   for s in doc['segments']:
    if s.get('speaker_name')!=role['person_name']or not s.get('speaker_category','').startswith('council_')or not s.get('person_id'):continue
    if role.get('person_id')and (s['person_id']!=role['person_id']or m['term']!=role['term']):continue
    if role.get('candidate_person_ids')and s['person_id']not in role['candidate_person_ids']:continue
    proof=match(body,text[s['content_start']:s['char_end']])
    if proof:proofs[aid].append({'text':body,'method':'complete_body_within_verified_member_speech','meeting_id':m['meeting_id'],'segment_id':s['segment_id'],'source_sha256':m['sha256'],'meeting_url':m['official_url']})
 eligible=[];held=[];counts=collections.Counter();kinds={}
 for aid,(role,src)in lookup.items():
  matches=proofs[aid];reasons=reasons_for(role['analysis_gate'],len(matches));item={'activity_id':aid,'person_id':role.get('person_id'),'person_name':role['person_name'],'date':role['date'],'term':role.get('term'),'source_dataset':role['source_dataset'],'activity_url':role['official_url'],'activity_body_sha256':sha((src.get('body_text')or'').encode()),'text_input_eligible':not reasons,'hold_reasons':reasons,'source_content_proofs':[{k:v for k,v in p.items()if k!='text'}for p in matches],'committee_weighting_ready':False,'interest_score_ready':False}
  if not reasons:item['member_text']=matches[0]['text'];item['member_text_sha256']=sha(item['member_text'].encode())
  (held if reasons else eligible).append(item);counts.update(reasons);k=kinds.setdefault(role['source_dataset'],{'records':0,'eligible':0,'held':0});k['records']+=1;k['held'if reasons else'eligible']+=1
 outputs={}
 for label,rows in [('eligible',eligible),('held',held)]:
  payload=pack(b''.join(encoded(r)for r in rows));name=f'{label}_member_text_inputs.jsonl.gz';(out/name).write_bytes(payload);outputs[label]={'file':name,'rows':len(rows),'sha256':sha(payload),'bytes':len(payload)}
 report={'schema':'cheongju-member-text-inputs/1','status':'PASS','source_records':len(lookup),'eligible_text_records':len(eligible),'held_text_records':len(held),'datasets':kinds,'hold_reasons':dict(counts),'identity_promotions':0,'date_changes':0,'official_site_requests':0,'interest_scores_computed':0}
 write_json(out/'member_text_inputs_manifest.json',{'schema':'cheongju-member-text-input-release/1','script_sha256':sha(Path(__file__).read_bytes()),'source_gate_manifest_sha256':sha((out/'analysis_activity_gate_manifest.json').read_bytes()),'source_question_parts_sha256':sha((out/'question_answer_parts.json').read_bytes()),'source_index_sha256':sha(idxraw),'outputs':outputs});write_json(root/'reports/member-text-inputs-latest.json',report);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(build(a.root),ensure_ascii=False,indent=2))
