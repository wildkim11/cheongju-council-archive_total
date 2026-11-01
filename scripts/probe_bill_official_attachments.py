"""Read-only one-time official-source attachment/link discovery, not data promotion.

Limit the source requests to the twelve known exceptional bill detail pages
and the separately verified public notice for bill 2258. Store only metadata,
a page digest, short visible snippets, and attachment-related link attributes.
"""
from __future__ import annotations
import datetime as dt, hashlib, html as html_lib, json, re
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from collect_bills import fetch_any, _visible

ROOT=Path(__file__).resolve().parents[1]
TARGET_IDS={"1308","1458","2083","2258","2364","2637","3255","375","2177","2180","3265","3266"}
NOTICE="https://council.cheongju.go.kr/content/news/lawNoticeList.html?fidx=10627&opt=&page=45&pg=vv&sid=1000&sword="
ALLOWED={"council.cheongju.go.kr","councilrec.cheongju.go.kr"}
PATTERN=re.compile(r"file|down|attach|첨부|미리보기|hwp|hwpx|pdf|document|download",re.I)

def attr_map(tag):
    attrs={}
    for k,v in re.findall(r'([a-zA-Z_:][\w:.-]*)\s*=\s*["\']([^"\']*)["\']',tag):
        attrs[k.lower()]=html_lib.unescape(v)
    return attrs

def links(html,base):
    matches=[]
    for m in re.finditer(r"<(?:a|button|iframe|embed|input)\b[^>]*>",html,re.I):
        attr=attr_map(m.group(0))
        tail=html[m.end():m.end()+140]
        label=_visible(tail.split("</",1)[0])[:80]
        context=html[max(m.start()-140,0):min(m.end()+220,len(html))]
        if PATTERN.search(m.group(0)+" "+label+" "+context):
            attrs={k:v[:1000] for k,v in attr.items() if k in
                   ("href","onclick","src","data-src","data-url","value","id","class","title","name")}
            href=attrs.get("href") or attrs.get("src")
            if href and href.startswith(("http://","https://","/")):
                target=urljoin(base,href)
                if urlsplit(target).hostname not in ALLOWED:
                    target=None
            else:
                target=None
            matches.append({"tag":m.group(0).split()[0][1:],
                            "label":label,"attributes":attrs,"safe_absolute_url":target})
    uniq=[]
    keys=set()
    for match in matches:
        key=json.dumps(match,sort_keys=True,ensure_ascii=False)
        if key not in keys:
            uniq.append(match)
            keys.add(key)
    return uniq[:120]

def excerpt(html,needle):
    text=_visible(html)
    m=re.search(needle,text,re.I)
    if not m:
        return None
    return text[max(0,m.start()-150):m.end()+300]

def run(root=ROOT):
    existing=json.loads((root/"reports/bill-pending-and-institutional-source-qa.json").read_text(encoding="utf-8"))
    targets=existing["member_bills"]+existing["institutional_anomalies"]
    if {x["internal_number"] for x in targets}!=TARGET_IDS:
        raise ValueError("Unexpected 12-bill exception inventory")
    rows=[]
    for record in targets:
        b=record["raw_bill_fields"]
        url=b["official_url"]
        if urlsplit(url).hostname not in ALLOWED:
            raise ValueError("Unexpected official host")
        data={"internal_number":record["internal_number"],"term":b["term"],"title":b["title"],
              "proposer_type_list":b["proposer_type_list"],"official_url":url,
              "fetch_status":"unattempted"}
        try:
            raw=fetch_any(url)
            fields={key:excerpt(raw,key) for key in
                    ("대표발의자","공동발의","제안의원","첨부파일","기타파일","철회일자")}
            data.update({"fetch_status":"ok","html_bytes":len(raw.encode()),"html_sha256":hashlib.sha256(raw.encode()).hexdigest(),
                         "text_snippets":{k:v for k,v in fields.items() if v},
                         "attachment_related_elements":links(raw,url)})
        except Exception as e:
            data.update({"fetch_status":"error","exception":type(e).__name__,"message":str(e)[:240]})
        print(json.dumps({k:data[k] for k in ("internal_number","fetch_status")},ensure_ascii=False),flush=True)
        rows.append(data)
    notice={"official_url":NOTICE,"fetch_status":"unattempted"}
    try:
        raw=fetch_any(NOTICE)
        notice.update({"fetch_status":"ok","html_bytes":len(raw.encode()),"html_sha256":hashlib.sha256(raw.encode()).hexdigest(),
                       "title_excerpt":excerpt(raw,"한국아마추어무선연맹"),
                       "attachment_related_elements":links(raw,NOTICE)})
    except Exception as e:
        notice.update({"fetch_status":"error","exception":type(e).__name__,"message":str(e)[:240]})
    result={"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
            "scope":"read-only official HTML metadata probe; cannot by itself prove downloaded document content",
            "bill_details":rows,"bill_2258_official_public_notice":notice,
            "no_proposer_rows_modified":True,
            "ok_details":sum(x["fetch_status"]=="ok" for x in rows),
            "failed_details":sum(x["fetch_status"]=="error" for x in rows)}
    path=root/"reports/bill-official-source-link-probe.json"
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"ok_details":result["ok_details"],"failed_details":result["failed_details"],
                     "notice_status":notice["fetch_status"],
                     "notice_link_candidates":len(notice.get("attachment_related_elements",[])),
                     "detail_link_candidate_counts":{x["internal_number"]:len(x.get("attachment_related_elements",[])) for x in rows}},ensure_ascii=False))
    return result

if __name__=="__main__":
    run()
