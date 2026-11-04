"""Reproduce the three reviewed bill/minutes roster conflicts from preserved sources."""
import argparse,json,re
from pathlib import Path
from process_meeting_segments import sha,encoded,write_json
from audit_stage_c import markdown_parts,canon
ROOT=Path(__file__).resolve().parents[1]
CASES=(('2362','minutes-3070'),('2383','minutes-3105'),('2449','minutes-3148'))
def review(root=ROOT):
 root=Path(root);index_raw=(root/'indexes/integrated/meetings.json').read_bytes();bill_raw=(root/'archive/bills/items.json').read_bytes();index={x['legacy_minutes_id']:x for x in json.loads(index_raw)};bills={str(x['internal_number']):x for x in json.loads(bill_raw)};out=[]
 for bid,mid in CASES:
  b=bills[bid];m=index[mid];raw=(root/m['path']).read_bytes()
  if sha(raw)!=m['sha256']:raise ValueError('source meeting hash mismatch')
  _,_,body=markdown_parts(raw.decode());
  if sha(canon(body).encode())!=m['content_sha256']:raise ValueError('source meeting body mismatch')
  evidence=[]
  for n,line in enumerate(raw.decode().splitlines(),1):
   if b['title'] not in line:continue
   groups=re.findall(r'\(([^()]+)의원 발의\)',line)
   if not groups:continue
   names_raw=[x.strip()for x in groups[-1].split(',')];names=[re.sub(r'\s+','',name)for name in names_raw]
   if not all(re.fullmatch(r'[가-힣]{2,5}',name)for name in names) or len(names)!=len(set(names)):raise ValueError('roster label not safely parsed')
   evidence.append({'line_1based':n,'excerpt':line,'excerpt_sha256':sha(line.encode()),'names_raw':names_raw,'names':names})
  if len(evidence)<2 or len({tuple(x['names'])for x in evidence})!=1:raise ValueError('two agreeing explicit roster labels required')
  names=set(evidence[0]['names']);saved=set(b['full_proposer_names'])
  if not set(b['representative_proposers'])<=names:raise ValueError('representative absent from minutes label')
  out.append({'internal_number':bid,'title':b['title'],'proposal_date':b['proposal_date'],'bill_official_url':b['official_url'],'bill_record_sha256':sha(encoded(b)),'meeting_id':m['meeting_id'],'meeting_date':m['date'],'meeting_official_url':m['official_url'],'source_path':m['path'],'source_sha256':m['sha256'],'saved_roster_count':len(saved),'minutes_roster_count':len(names),'saved_only':sorted(saved-names),'minutes_only':sorted(names-saved),'evidence':evidence,'review_status':'preserved_official_minutes_support_hold_not_live_bill_detail_verification'})
 result={'schema':'cheongju-reviewed-bill-minute-roster-conflicts/1','source_index_sha256':sha(index_raw),'source_bills_sha256':sha(bill_raw),'official_site_requests':0,'normalization':'Whitespace removed inside explicit comma-separated Korean names; raw labels retained','cases':out};write_json(root/'reports/reviewed-temporal-bill-minute-evidence.json',result);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();r=review(a.root);print(json.dumps([{'bill':x['internal_number'],'saved':x['saved_roster_count'],'minutes':x['minutes_roster_count'],'saved_only':x['saved_only']}for x in r['cases']],ensure_ascii=False))
