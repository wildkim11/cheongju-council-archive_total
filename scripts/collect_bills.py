"""Collect official bill/resolution metadata and full proposer rosters for integrated terms 1-4."""
from __future__ import annotations
import argparse, datetime as dt, html as html_lib, json, re, ssl, urllib.parse, urllib.request
from pathlib import Path

from archive_common import save_json
from collect_integrated_minutes import fetch as fetch_minutes_host

ROOT=Path(__file__).resolve().parents[1]
BASE="https://council.cheongju.go.kr"
LIST_URL=f"{BASE}/content/activity/billForProcessing.html"
COUNCIL_SCOPE="cheongju_integrated"
TERMS=(1,2,3,4)
TLS=ssl.create_default_context()
TLS.minimum_version=ssl.TLSVersion.TLSv1_2

def fetch_main(url:str)->str:
    p=urllib.parse.urlsplit(url)
    if p.scheme!="https" or p.netloc!="council.cheongju.go.kr":
        raise ValueError("Unexpected main-site source host")
    req=urllib.request.Request(url,headers={"User-Agent":"CheongjuCouncilArchive/0.1"})
    with urllib.request.urlopen(req,timeout=40,context=TLS) as resp:
        if resp.status!=200: raise ValueError(f"Official source HTTP {resp.status}")
        return resp.read().decode("utf-8-sig","replace")

def fetch_any(url:str)->str:
    p=urllib.parse.urlsplit(url)
    if p.netloc=="council.cheongju.go.kr":
        return fetch_main(url)
    if p.netloc=="councilrec.cheongju.go.kr":
        return fetch_minutes_host(url)
    raise ValueError("Unexpected bill source host")

def _visible(raw:str)->str:
    raw=re.sub(r"<br\s*/?>"," ",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",html_lib.unescape(raw)).strip()

def _absolute(base:str,href:str)->str:
    return urllib.parse.urljoin(base,href)

def _internal_number(url:str)->str|None:
    q=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    return (q.get("number") or [None])[0]

def parse_list_page(html:str,term:int,source_url:str)->list[dict]:
    rows=[];seen=set()
    for tr in re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>",html,flags=re.I):
        link=re.search(
            r'<a\b[^>]*href=["\']([^"\']*iframe_bill_view1\.html[^"\']*)["\'][^>]*>([\s\S]*?)</a>',
            tr,flags=re.I,
        )
        if not link: continue
        href,title_raw=link.group(1),link.group(2)
        url=_absolute(source_url,href)
        internal=_internal_number(url)
        if not internal or internal in seen: continue
        seen.add(internal)
        cells=[_visible(x) for x in re.findall(r"<t[dh]\b[^>]*>([\s\S]*?)</t[dh]>",tr,flags=re.I)]
        title=_visible(title_raw)
        bill_number=cells[0] if cells else None
        session=cells[1] if len(cells)>1 else None
        proposer_type=cells[3] if len(cells)>3 else None
        committee=cells[4] if len(cells)>4 else None
        result=cells[5] if len(cells)>5 else None
        processed_date=cells[6] if len(cells)>6 else None
        rows.append({
            "internal_number":internal,
            "council_scope":COUNCIL_SCOPE,
            "term":term,
            "bill_number_list":bill_number,
            "session_list":session,
            "title":title,
            "proposer_type_list":proposer_type,
            "committee_list":committee or None,
            "result_list":result or None,
            "processed_date_list":processed_date or None,
            "official_url":url,
            "list_source_url":source_url,
        })
    return rows

def _field(text:str,label:str,next_labels:list[str])->str|None:
    labs="|".join(re.escape(x) for x in next_labels)
    tail=rf"(?=\s+(?:{labs})\s*[:|]?|$)" if labs else r"$"
    m=re.search(rf"{re.escape(label)}\s*[:|]?\s*(.+?){tail}",text,re.S)
    return re.sub(r"\s+"," ",m.group(1)).strip(" |") if m else None

def _names(value:str|None)->list[str]:
    if not value: return []
    stop={
        "대표발의자","공동발의","발의자","위원회","본회의","처리결과",
        "원안가결","수정가결","부결","철회","의원","위원장","의장",
        "시장","청주시장","위원회안","위원회","집행기관"
    }
    out=[]
    # names may contain an internal space such as 허 선
    cleaned=re.sub(r"(?<=[가-힣])\s+(?=[가-힣])","",value)
    for n in re.findall(r"[가-힣]{2,5}",cleaned):
        if n not in stop and n not in out: out.append(n)
    return out

def parse_detail(html:str,row:dict)->dict:
    text=_visible(html)
    text=re.sub(r"발\s*의\s*자","발의자",text)
    text=re.sub(r"발\s*의\s*일","발의일",text)
    labels=[
        "의안번호","의안종류","발의자","발의일","회기","소관위원회",
        "제안의원","대표발의자","공동발의","위원회","본회의",
        "집행기관","이송일","공포일","공포번호","철회일자","비고",
        "첨부파일","기타파일"
    ]
    bill_number=_field(text,"의안번호",labels)
    bill_type=_field(text,"의안종류",labels)
    proposer_type=_field(text,"발의자",labels)
    proposal_date=_field(text,"발의일",labels)
    session=_field(text,"회기",labels)
    committee=_field(text,"소관위원회",labels)
    representative_text=_field(text,"대표발의자",labels)
    co_text=_field(text,"공동발의",labels)

    representative=_names(representative_text)
    co_proposers=_names(co_text)
    full=[]
    for n in representative+co_proposers:
        if n not in full: full.append(n)

    # Some official detail renderings duplicate the proposer table and may place
    # the representative last. Preserve both parsed components and the union.
    return {
        **row,
        "bill_number":bill_number or row.get("bill_number_list"),
        "bill_type":bill_type,
        "proposer_type":proposer_type or row.get("proposer_type_list"),
        "proposal_date":proposal_date,
        "session":session or row.get("session_list"),
        "committee":committee or row.get("committee_list"),
        "representative_proposer_text":representative_text,
        "co_proposers_text":co_text,
        "representative_proposers":representative,
        "co_proposers":co_proposers,
        "full_proposer_names":full,
        "detail_text_checked":True,
    }

def discover_term(term:int,max_pages:int=300)->list[dict]:
    all_rows=[];seen=set();empty=0
    for page in range(1,max_pages+1):
        url=f"{LIST_URL}?daesu={term}&page={page}"
        html=fetch_main(url)
        rows=parse_list_page(html,term,url)
        new=[r for r in rows if r["internal_number"] not in seen]
        for r in new: seen.add(r["internal_number"]);all_rows.append(r)
        if not rows:
            empty+=1
            if page>1 and empty>=2: break
        else:
            empty=0
    if not all_rows:
        raise ValueError(f"No official bill rows discovered for term {term}")
    return all_rows

def collect(root:Path=ROOT,terms:tuple[int,...]=TERMS)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    rows=[];by_term={}
    for term in terms:
        listed=discover_term(term)
        detailed=[]
        for i,row in enumerate(listed,1):
            parsed=parse_detail(fetch_any(row["official_url"]),row)
            parsed["checked_at"]=stamp
            detailed.append(parsed)
        by_term[str(term)]=len(detailed);rows.extend(detailed)

    # The official internal number is the stable source key within this source family.
    dedup={}
    for row in rows:
        key=row["internal_number"]
        prior=dedup.get(key)
        if prior and prior["term"]!=row["term"]:
            raise ValueError(f"Internal bill number reused across terms unexpectedly: {key}")
        dedup[key]=row
    rows=sorted(dedup.values(),key=lambda r:(r["term"],int(r["internal_number"])))
    save_json(root/"archive/bills/items.json",rows)
    report={
        "checked_at":stamp,
        "council_scope":COUNCIL_SCOPE,
        "records":len(rows),
        "by_term":by_term,
        "with_full_proposer_roster":sum(bool(r["full_proposer_names"]) for r in rows),
        "resolution_like":sum((r.get("bill_type") or "") in {"결의안","건의안"} for r in rows),
    }
    save_json(root/"reports/bills.json",report)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--term",type=int,choices=TERMS)
    args=p.parse_args()
    terms=(args.term,) if args.term else TERMS
    print(json.dumps(collect(terms=terms),ensure_ascii=False))

if __name__=="__main__":
    main()
