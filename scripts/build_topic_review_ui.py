"""Build an offline human review packet from verified release snapshots."""
import argparse,json
from pathlib import Path
from compare_topic_reviews import ROOT,load_release
from process_meeting_segments import sha

def build(root=ROOT,codebook_path=None,template_path=None):
 root=Path(root);folder=root/'exports/topic-review';tm,tasks=load_release(folder,'manifest.json','development_sample');dm,drafts=load_release(folder,'draft_manifest.json','draft_review');bookraw=(Path(codebook_path)if codebook_path else root/'config/policy_topics_v1.json').read_bytes();book=json.loads(bookraw)
 if sha(bookraw)!=tm['codebook_sha256']or dm['codebook_sha256']!=tm['codebook_sha256']or dm['source_task_manifest_sha256']!=sha((folder/'manifest.json').read_bytes()):raise ValueError('review UI snapshot mismatch')
 if any(sha(r['member_text'].encode())!=r['member_text_sha256']for r in tasks):raise ValueError('review text hash mismatch')
 if len({r['case_id']for r in tasks})!=len(tasks):raise ValueError('duplicate review cases')
 payload={'snapshot':sha((folder/'manifest.json').read_bytes()),'book':book,'tasks':tasks,'drafts':{d['case_id']:d for d in drafts}}
 # Escaping '<' prevents source quotations from terminating the JSON script element.
 data=json.dumps(payload,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
 template=(Path(template_path)if template_path else root/'web/topic_review.html').read_text();html=template.replace('/*REVIEW_PAYLOAD*/',data)
 path=folder/'review.html';path.write_text(html);return path
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(build(a.root))
