"""Scheduled macOS collection over a disposable candidate; publish validated facts only.

Existing live run_sync interlock remains intact. This controller uses its public
candidate-root API, then the existing journaled transaction to publish after QA.
No identity candidate promotion, political judgments, or HTML generation.
"""
from __future__ import annotations
import argparse,contextlib,datetime as dt,gzip,hashlib,importlib,json,shutil,tempfile,threading,time,urllib.parse,urllib.request
from pathlib import Path
from unittest.mock import patch
from archive_common import save_json
import sync_transaction
import collection_policy

ROOT=Path(__file__).resolve().parents[1]
FAMILIES=('minutes','bills','activities','people','groups','media','attachments')
HOSTS={'council.cheongju.go.kr','councilrec.cheongju.go.kr'}
def load(p,default):return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default

def select_family(state,requested,now):
    if requested!='auto':return requested
    # A failed family never prevents other source families from receiving a turn.
    i=int(state.get('cursor',0));state['cursor']=i+1
    return FAMILIES[i%len(FAMILIES)]

def preserved_merge(old,new,key):
    """A missing list item is retained, never interpreted as official deletion."""
    result={str(x[key]):x for x in old}
    if len(result)!=len(old):raise ValueError('duplicate saved source ID')
    seen=set()
    for x in new:
        k=str(x[key])
        if k in seen:raise ValueError('duplicate discovered source ID')
        seen.add(k);result[k]=x
    return sorted(result.values(),key=lambda x:str(x[key]))

def refresh_board(root,module,kind=None,width=20,ordinal=0):
    """Discover all pages, fetch new details plus recent and rotating saved ones."""
    cfg=module.CONFIG[kind];old=load(root/cfg['output'],[])
    listed=module.discover_links(cfg['list_url'],cfg['detail_pattern'])
    index={str(x['source_id']):x for x in old}
    numeric=lambda x:int(x['source_id'])
    ordered=sorted(listed,key=numeric,reverse=True)
    rotate=sorted(index,key=int);start=(ordinal*width)%max(1,len(rotate))
    chosen={str(x['source_id']) for x in ordered[:width]}
    chosen.update((rotate+rotate)[start:start+min(width,len(rotate))])
    # Recheck bounded reviewed date conflicts in the normal macOS source cycle.
    # Only IDs rediscovered in the official list are fetched, never report URLs.
    review=load(root/'reports/activity-date-discrepancies.json',{})
    reviewed=set()
    if review.get('schema')=='cheongju-activity-date-review/1':
        dataset=Path(cfg['output']).stem
        for item in review.get('rows',[]):
            parts=item.get('activity_id','').split(':')
            if item.get('source_dataset')==dataset and len(parts)==3 and parts[0]==dataset and parts[1].isdigit():reviewed.add(parts[1])
    listed_ids={str(r['source_id']) for r in listed}
    reviewed=sorted(reviewed&listed_ids,key=int)[:width]
    chosen.update(reviewed)
    rows=[]
    for r in listed:
        sid=str(r['source_id'])
        if sid not in index or sid in chosen:
            cfgarg=cfg['section_label'] if module.__name__=='collect_speeches_questions' else cfg
            parsed=module.parse_detail(module.fetch_text(r['official_url']),r,cfgarg)
            parsed.update(activity_type=kind,council_scope='cheongju_integrated',checked_at=dt.datetime.now(dt.timezone.utc).isoformat());rows.append(parsed)
    save_json(root/cfg['output'],preserved_merge(old,rows,'source_id'))
    return {'listed':len(listed),'details_checked':len(rows),'saved':len(index),'review_priority_ids':reviewed,'missing_saved_ids_retained':sorted(set(index)-{str(r['source_id']) for r in listed})}

class Capture:
    def __init__(self,root):self.root=root;self.rows=[];self.lock=threading.Lock();self.stack=contextlib.ExitStack();self.failures=[]
    def wrap(self,fn):
        def fetch(url,*args,**kwargs):
            host=urllib.parse.urlsplit(url).hostname
            if host not in HOSTS:raise ValueError('unexpected official host')
            try:text=fn(url,*args,**kwargs)
            except Exception as e:
                with self.lock:self.failures.append({'url':url,'error':type(e).__name__+': '+str(e)[:200]})
                raise
            raw=text.encode('utf-8');digest=hashlib.sha256(raw).hexdigest();p=self.root/'archive/source_responses'/f'{digest}.html.gz'
            with self.lock:
                if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(raw,mtime=0))
                self.rows.append({'url':url,'request_parameters_sha256':hashlib.sha256(json.dumps(args[0] if args else kwargs.get('params'),sort_keys=True).encode()).hexdigest(),'decoded_utf8_sha256':digest,'path':str(p.relative_to(self.root)),'bytes':len(raw)})
            return text
        return fetch
    def __enter__(self):
        # Patch public transport aliases used by the original parsers. TLS/retry
        # behavior stays in the original collectors, not a new alternate host.
        modules=['collect_current_members','activity_common','collect_speeches_questions','collect_board_activities','collect_written_questions','collect_photo_activity','collect_current_committees','collect_historical_committees','collect_current_research_groups','collect_historical_research_metadata']
        for n in modules:
            m=importlib.import_module(n)
            if hasattr(m,'fetch_text'):self.stack.enter_context(patch.object(m,'fetch_text',self.wrap(m.fetch_text)))
        for n,attr in [('collect_integrated_minutes','fetch'),('collect_bills','fetch_main'),('collect_bills','fetch_minutes_host')]:
            m=importlib.import_module(n);self.stack.enter_context(patch.object(m,attr,self.wrap(getattr(m,attr))))
        h=importlib.import_module('collect_integrated_historical_members');original=h.Session.text;capture=self
        def session_text(session,url,data=None):return capture.wrap(lambda u,d:original(session,u,d))(url,data)
        self.stack.enter_context(patch.object(h.Session,'text',session_text))
        return self
    def __exit__(self,*args):return self.stack.__exit__(*args)

def preserve_response_manifest(root,family,started_at,rows):
    # Keep provenance for every successful collection, not just the last family.
    for row in rows:
        rel=Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts or rel.parts[:2]!=('archive','source_responses'):
            raise ValueError('unsafe source-response path')
        raw=gzip.decompress((root/rel).read_bytes())
        if hashlib.sha256(raw).hexdigest()!=row['decoded_utf8_sha256']:
            raise ValueError('source-response hash mismatch')
    document={'schema':'cheongju-source-responses/1','family':family,'collection_started_at':started_at,'responses':rows}
    raw=(json.dumps(document,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    rel=Path('archive/source_responses/manifests')/(hashlib.sha256(raw).hexdigest()+'.json')
    (root/rel).parent.mkdir(parents=True,exist_ok=True);(root/rel).write_bytes(raw)
    return str(rel)

def download_attachments(root,limit=20,max_bytes=8*1024*1024,retry_only=False):
    queue=load(root/'reports/automatic/attachments.json',{})
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if isinstance(v,str) and k in {'official_url','question_file_url','answer_file_url'}:
                    u=urllib.parse.urlsplit(v)
                    if u.scheme=='https' and u.hostname in HOSTS and any(t in v.lower() for t in ('download','paper_down','.pdf','.hwp','.hwpx','.xlsx','.docx')):queue.setdefault(v,{'status':'pending','attempts':0})
                elif isinstance(v,(dict,list)):walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    for folder in ('archive/activities','archive/research_groups','archive/bills'):
        for p in (root/folder).glob('*.json'):walk(load(p,[]))
    now=dt.datetime.now(dt.timezone.utc).isoformat();attempted=0
    class OfficialRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            u=urllib.parse.urlsplit(newurl)
            if u.scheme!='https' or u.hostname not in HOSTS:raise ValueError('unexpected attachment redirect')
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    opener=urllib.request.build_opener(OfficialRedirect())
    for url,item in sorted(queue.items(),key=lambda kv:(kv[1].get('attempts',0),kv[0])):
        if retry_only and item['status']!='failed':continue
        if item['status']=='downloaded' or item.get('next_retry_at','')>now:continue
        if attempted>=limit:break
        attempted+=1;item['attempts']+=1
        try:
            time.sleep(.3)
            with opener.open(urllib.request.Request(url,headers={'User-Agent':'CheongjuCouncilArchive/0.2'}),timeout=40) as response:
                raw=response.read(max_bytes+1)
                if len(raw)>max_bytes:raise ValueError('attachment exceeds per-file archive limit')
                if not raw.startswith((b'%PDF',b'PK\x03\x04',b'\xd0\xcf\x11\xe0')):raise ValueError('unexpected document signature; not counted as downloaded')
            digest=hashlib.sha256(raw).hexdigest();path=root/'archive/attachments'/f'{digest}.bin';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            item.update(status='downloaded',sha256=digest,bytes=len(raw),path=str(path.relative_to(root)),checked_at=now);item.pop('error',None)
        except Exception as e:
            item.update(status='failed',error=str(e)[:240],next_retry_at=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=min(24,2**min(item['attempts'],5)))).isoformat())
    save_json(root/'reports/automatic/attachments.json',queue)
    return {'queued':len(queue),'attempted':attempted,'downloaded_total':sum(x['status']=='downloaded' for x in queue.values()),'failed_total':sum(x['status']=='failed' for x in queue.values())}

def execute(family,root,ordinal,retry_only=False):
    if family=='minutes':
        import collect_integrated_minutes as c
        old=load(root/'indexes/integrated/meetings.json',[]);published=sorted([x for x in old if x['publication_status']=='published'],key=lambda x:x['meeting_id']);i=(ordinal*8)%max(1,len(published));forced={x['meeting_id'] for x in (published+published)[i:i+min(8,len(published))]}
        return c.run_sync('incremental',root,force_body_ids=forced)
    if family=='bills':
        import collect_bills as b,link_bill_proposers as links
        old=load(root/'archive/bills/items.json',[]);by={str(x['internal_number']):x for x in old};listed=[r for term in b.TERMS for r in b.discover_term(term)];ordered=sorted(listed,key=lambda r:int(r['internal_number']),reverse=True);ids=sorted(by,key=int);i=(ordinal*20)%max(1,len(ids));chosen={str(x['internal_number']) for x in ordered[:20]}|set((ids+ids)[i:i+min(20,len(ids))]);new=[];review=[]
        for r in listed:
            k=str(r['internal_number'])
            if k in by and k not in chosen:continue
            parsed=b.parse_detail(b.fetch_any(r['official_url']),r);prior=by.get(k)
            # Previously repaired full rosters must not be replaced by a parser
            # reading an incomplete official display. Preserve for review.
            if prior and any(prior.get(f)!=parsed.get(f) for f in ('full_proposer_names','representative_proposers','co_proposers')):
                review.append({'internal_number':k,'saved':prior,'observed':parsed});continue
            parsed['checked_at']=dt.datetime.now(dt.timezone.utc).isoformat();new.append(parsed)
        save_json(root/'archive/bills/items.json',preserved_merge(old,new,'internal_number'));save_json(root/'reports/automatic/bill_roster_review.json',preserved_merge(load(root/'reports/automatic/bill_roster_review.json',[]),review,'internal_number'));links.link(root)
        return {'listed':len(listed),'details_checked':len(new)+len(review),'roster_changes_for_review':len(review)}
    if family=='activities':
        import collect_speeches_questions as m,collect_written_questions as w
        out={k:refresh_board(root,m,k,ordinal=ordinal) for k in m.CONFIG};old=load(root/'archive/activities/written_questions.json',[]);out['written']=w.collect(root);save_json(root/'archive/activities/written_questions.json',preserved_merge(old,load(root/'archive/activities/written_questions.json',[]),'source_id'));return out
    if family=='people':
        import collect_current_members as p,collect_integrated_historical_members as h,collect_term4_departed_members as d,build_identity_candidates as i
        return {'current':p.run(root),'historical':h.collect(root),'departed':d.collect(root),'identity_candidates':i.build(root)}
    if family=='groups':
        out={}
        for name in ('collect_current_committees','collect_historical_committees','collect_current_research_groups','collect_historical_research_metadata'):out[name]=importlib.import_module(name).collect(root)
        return out
    if family=='media':
        import collect_board_activities as b,collect_photo_activity as p
        out={k:refresh_board(root,b,k,ordinal=ordinal) for k in b.CONFIG if k!='photo'};old=load(root/'archive/activities/photo_activity.json',[]);out['photo']=p.collect(root);save_json(root/'archive/activities/photo_activity.json',preserved_merge(old,load(root/'archive/activities/photo_activity.json',[]),'source_id'));return out
    if family=='attachments':return download_attachments(root,retry_only=retry_only)
    raise ValueError('unknown collection family')

def validate_candidate(stage,oldroot):
    import validate_archive,export_analyzer,audit_stage_c
    # Never allow an incomplete inventory to erase existing meetings.
    old=load(oldroot/'indexes/integrated/meetings.json',[]);new=load(stage/'indexes/integrated/meetings.json',[]);history=load(stage/'indexes/integrated/meeting_history.json',[])
    if {x['meeting_id'] for x in old}-{x['meeting_id'] for x in new+history}:raise ValueError('saved meetings missing from candidate and history')
    export_analyzer.export(stage);validate_archive.validate(stage);qa=audit_stage_c.audit(stage)
    if qa['status']!='PASS':raise ValueError('candidate archive QA failed: '+str(qa['errors'][:10]))
    import audit_written_question_links
    qa['written_question_links']=audit_written_question_links.build(stage)
    if qa['written_question_links']['status']!='PASS':raise ValueError('written question link provenance audit failed')
    # Offline processing consumes only this verified candidate, before publication.
    import process_meeting_segments,verify_processing
    process_meeting_segments.process(stage)
    import resolve_activity_spacing_matches
    linking=resolve_activity_spacing_matches.resolve(stage)
    qa['activity_spacing_linking']=linking
    import build_question_answer_parts
    qa['question_answer_parts']=build_question_answer_parts.build(stage)
    import review_question_identity_evidence
    qa['question_identity_evidence']=review_question_identity_evidence.review(stage)
    import resolve_question_answer_links
    qa['question_answer_linking']=resolve_question_answer_links.resolve(stage)
    processing=verify_processing.verify(stage)
    save_json(stage/'reports/processing-qa-latest.json',processing)
    qa['processing']=processing
    import review_activity_date_discrepancies
    qa['activity_date_review']=review_activity_date_discrepancies.review(stage)
    import review_single_activity_differences
    qa['single_activity_differences']=review_single_activity_differences.review(stage)
    # HTML consumers must receive text packs from this same verified snapshot.
    # Export failures abort the candidate before any live snapshot is published.
    import export_minutes_text
    qa['minutes_text']=export_minutes_text.export(stage)
    import build_activity_temporal_context
    qa['temporal_context']=build_activity_temporal_context.build(stage)
    import build_analysis_activity_gate
    qa['analysis_activity_gate']=build_analysis_activity_gate.build(stage)
    import build_member_activity_counts
    qa['member_activity_counts']=build_member_activity_counts.build(stage)
    import build_member_text_inputs
    qa['member_text_inputs']=build_member_text_inputs.build(stage)
    import build_topic_review_materials
    qa['topic_review_materials']=build_topic_review_materials.build(stage,codebook_path=oldroot/'config/policy_topics_v1.json')
    import build_topic_review_drafts
    qa['topic_review_drafts']=build_topic_review_drafts.build(stage,codebook_path=oldroot/'config/policy_topics_v1.json')
    import build_topic_review_ui
    build_topic_review_ui.build(stage,codebook_path=oldroot/'config/policy_topics_v1.json',template_path=oldroot/'web/topic_review.html')
    qa['topic_review_ui']={'file':'exports/topic-review/review.html','human_reviews_created':0}
    return qa

def run(root=ROOT,family='auto',runner=execute,validator=validate_candidate,retry_now=False,retry_attempt=False):
    root=Path(root);state=load(root/'reports/automatic/collection_state.json',{'schema':'cheongju-auto-collection/1','cursor':0,'families':{}});now=dt.datetime.now(dt.timezone.utc);selected=select_family(state,family,now);slot=state['families'].setdefault(selected,{'attempts':0});report={'family':selected,'started_at':now.isoformat(),'status':'FAILED','published':False}
    if retry_attempt and not collection_policy.failed_due(slot,now):
        report.update(status='DEFERRED',reason='no due failed source or daily retry budget exhausted');save_json(root/'reports/automatic-collection-latest.json',report);return report
    if retry_attempt:
        count=slot.get('retry_attempts_today',0) if slot.get('retry_attempts_day')==collection_policy.day(now) else 0
        slot.update(retry_attempts_day=collection_policy.day(now),retry_attempts_today=count+1)
    if not retry_now and not retry_attempt and slot.get('next_retry_at','')>now.isoformat():report['status']='DEFERRED';state['last_run']=report;save_json(root/'reports/automatic/collection_state.json',state);save_json(root/'reports/automatic-collection-latest.json',report);return report
    slot['attempts']+=1
    capture=None
    try:
        with sync_transaction.exclusive_lock(root):
            sync_transaction.recover_pending(root)
            with tempfile.TemporaryDirectory(prefix='cheongju-auto-candidate-') as td:
                stage=Path(td)
                for name in ('archive','indexes','reports','exports'):
                    if (root/name).exists():shutil.copytree(root/name,stage/name)
                prior_rows=load(stage/'reports/automatic/source-response-latest.json',[])
                if prior_rows and not (stage/'reports/automatic/source-response-latest-metadata.json').exists():
                    successful=[(v['last_success_at'],k) for k,v in state['families'].items() if v.get('last_success_at')]
                    if successful:
                        stamp,name=max(successful);preserve_response_manifest(stage,name,stamp,prior_rows)
                with Capture(stage) as capture:
                    report['collection']=runner(selected,stage,now.toordinal(),retry_only=True) if runner is execute and retry_attempt else runner(selected,stage,now.toordinal())
                manifest=preserve_response_manifest(stage,selected,now.isoformat(),capture.rows)
                save_json(stage/'reports/automatic/source-response-latest-metadata.json',{'family':selected,'collection_started_at':now.isoformat(),'manifest':manifest})
                save_json(stage/'reports/automatic/source-response-latest.json',capture.rows)
                report['qa']=validator(stage,root);(stage/sync_transaction.LOCK).unlink(missing_ok=True);report['transaction']=sync_transaction.publish_staged_snapshot(stage,root);report.update(status='PASS',published=True)
        if selected=='attachments':
            queue=load(root/'reports/automatic/attachments.json',{});failed=[x for x in queue.values() if x.get('status')=='failed']
            slot.update(failed_documents=len(failed),pending_attachment_retry_at=min((x.get('next_retry_at',now.isoformat()) for x in failed),default=None))
        slot.update(last_success_at=now.isoformat(),consecutive_failures=0);slot.pop('next_retry_at',None);slot.pop('last_error',None)
    except Exception as e:
        fails=slot.get('consecutive_failures',0)+1;slot.update(consecutive_failures=fails,last_error=type(e).__name__+': '+str(e)[:500],next_retry_at=(now+dt.timedelta(minutes=min(1440,60*2**min(fails-1,5)))).isoformat());report['error']=slot['last_error']
        if capture:report['failed_requests']=capture.failures
    # Keep durable operational status even when no source snapshot was accepted.
    state['last_run']=report;save_json(root/'reports/automatic/collection_state.json',state);save_json(root/'reports/automatic-collection-latest.json',report)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--retry-attempt',action='store_true');p.add_argument('--retry-now',action='store_true',help='Explicit retry after a code fix; normal schedule honors backoff');p.add_argument('--family',choices=('auto',)+FAMILIES,default='auto');a=p.parse_args();result=run(family=a.family,retry_now=a.retry_now,retry_attempt=a.retry_attempt);print(json.dumps({k:v for k,v in result.items() if k!='qa'},ensure_ascii=False,indent=2));raise SystemExit(0 if result['status'] in ('PASS','DEFERRED') else 1)
if __name__=='__main__':main()
