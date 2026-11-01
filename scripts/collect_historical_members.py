"""Historical member adapters for official council pages.

Source facts only. Same-name people across terms are not automatically merged unless
an official stable identifier exists. Identity resolution is a separate, auditable step.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import ssl
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from archive_common import save_json, sha256_bytes

ROOT=Path(__file__).resolve().parents[1]
BASE="https://council.cheongju.go.kr"
TLS=ssl.create_default_context()
TLS.minimum_version=ssl.TLSVersion.TLSv1_2

OLD_CITY_PAGES={
    4:f"{BASE}/oldcity/content/member4.html",
    5:f"{BASE}/oldcity/content/member5.html",
    6:f"{BASE}/oldcity/content/member6.html",
    7:f"{BASE}/oldcity/content/member7.html",
    8:f"{BASE}/oldcity/content/member8.html",
    9:f"{BASE}/oldcity/content/member9.html",
}
# The legacy county site uses page filenames that are not reliable term identifiers.
# Therefore the displayed official heading is parsed and must match the expected term.
OLD_COUNTY_PAGES={
    1:f"{BASE}/oldgun/content/member4.html",
    2:f"{BASE}/oldgun/content/member5.html",
    3:f"{BASE}/oldgun/content/member6.html",
    4:f"{BASE}/oldgun/content/member7.html",
    5:f"{BASE}/oldgun/content/member8.html",
    6:f"{BASE}/oldgun/content/member9.html",
}
INTEGRATED_HISTORY_URL=f"{BASE}/content/member/integrationCheongju.html"


def _request(url:str)->tuple[bytes,str]:
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!="https" or parsed.netloc!="council.cheongju.go.kr":
        raise ValueError("Unexpected source host")
    req=urllib.request.Request(url,headers={"User-Agent":"CheongjuCouncilArchive/0.1"})
    with urllib.request.urlopen(req,timeout=40,context=TLS) as resp:
        if resp.status!=200:
            raise ValueError(f"Official source HTTP {resp.status}")
        return resp.read(), resp.headers.get_content_type()

def fetch(url:str)->str:
    data,_=_request(url)
    return data.decode("utf-8-sig")


class HistoricalMemberParser(HTMLParser):
    VOID={"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}
    BLOCK={"li","div","article","section","dd"}

    def __init__(self):
        super().__init__()
        self.depth=0
        self.blocks=[]
        self.current=None
        self.headings=[]
        self.heading=None

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ("h1","h2","h3","h4","h5","strong") and self.heading is None:
            self.heading=[]
        if tag in self.BLOCK and self.current is None:
            self.current={"depth":self.depth,"text":[],"images":[],"links":[]}
        if self.current is not None:
            if tag=="img" and attrs.get("src"):
                self.current["images"].append({"src":attrs["src"],"alt":attrs.get("alt","")})
            if tag=="a" and attrs.get("href"):
                self.current["links"].append(attrs["href"])
        if tag not in self.VOID:
            self.depth+=1

    def handle_endtag(self,tag):
        if tag not in self.VOID:
            self.depth=max(0,self.depth-1)
        if self.heading is not None and tag in ("h1","h2","h3","h4","h5","strong"):
            value=" ".join(self.heading).strip()
            if value:
                self.headings.append(value)
            self.heading=None
        if self.current is not None and tag in self.BLOCK and self.depth==self.current["depth"]:
            if self.current["images"]:
                self.blocks.append(self.current)
            self.current=None

    def handle_data(self,data):
        s=data.strip()
        if not s:
            return
        if self.heading is not None:
            self.heading.append(s)
        if self.current is not None:
            self.current["text"].append(s)


def _abs(url:str)->str:
    return urllib.parse.urljoin(BASE+"/",url)


def displayed_term(html:str)->int|None:
    # Official old-site pages visibly label themselves e.g. "5대의원".
    parser=HistoricalMemberParser(); parser.feed(html)
    candidates=[]
    for h in parser.headings:
        m=re.search(r"(?:제\s*)?(\d+)\s*대\s*의원",h)
        if m:
            candidates.append(int(m.group(1)))
    if candidates:
        # Prefer the last/most specific heading; nav often lists several terms first.
        return candidates[-1]
    text=re.sub(r"<[^>]+>"," ",html)
    m=re.search(r"(?:제\s*)?(\d+)\s*대\s*의원",text)
    return int(m.group(1)) if m else None


def _clean_name(value:str)->str|None:
    # Historical pages commonly encode alt text as "이름이름지역명".
    compact=re.sub(r"\s+","",value)
    repeated=re.match(r"^([가-힣]{2,5})\1",compact)
    if repeated:
        return repeated.group(1)

    # Some pages use "이름 의원" or a single visible name.
    member_label=re.search(r"([가-힣]{2,5})\s*의원",value)
    if member_label:
        return member_label.group(1)

    tokens=re.findall(r"[가-힣]{2,4}",value)
    stop={"의원소개","청주시의회","청원군의회","선거구","비례대표","대의원"}
    for t in tokens:
        if t not in stop and not t.endswith("의원소개"):
            return t
    return None

def parse_members(html:str,source_url:str)->list[dict]:
    p=HistoricalMemberParser(); p.feed(html)
    out=[]; seen=set()
    for block in p.blocks:
        text=" ".join(block["text"]).strip()
        image=block["images"][0] if block["images"] else None
        combined=((image or {}).get("alt","")+" "+text).strip()
        name=_clean_name(combined)
        if not name:
            continue
        portrait_url=_abs(image["src"]) if image and image.get("src") else None

        # Remove repeated name from visible block text and keep remaining text as source label.
        detail=re.sub(re.escape(name)," ",combined)
        detail=re.sub(r"\s+"," ",detail).strip(" -·,")
        key=(name,portrait_url,detail)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "name":name,
            "source_detail":detail or None,
            "portrait_source_url":portrait_url,
            "source_url":source_url,
        })
    return out


def candidate_person_id(scope:str,term:int,name:str,portrait_url:str|None)->str:
    # Historical static pages often provide no stable member code.
    # Do not merge same-name records across terms without evidence.
    basis=f"{scope}|{term}|{name}|{portrait_url or ''}".encode("utf-8")
    return "person-candidate-"+sha256_bytes(basis)[:16]


def _portrait_extension(content_type:str,url:str)->str:
    mapping={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}
    if content_type in mapping:
        return mapping[content_type]
    suffix=Path(urllib.parse.urlsplit(url).path).suffix.lower()
    return suffix if suffix in {".jpg",".jpeg",".png",".webp"} else ".img"

def _mirror_portrait(root:Path,pid:str,url:str,stamp:str)->dict:
    data,content_type=_request(url)
    ext=_portrait_extension(content_type,url)
    local_path=f"archive/people/portraits/{pid}{ext}"
    path=root/local_path
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)
    return {
        "source_url":url,
        "local_path":local_path,
        "checked_at":stamp,
        "sha256":sha256_bytes(data),
    }

def collect_static_scope(scope:str,pages:dict[int,str],root:Path=ROOT,save_portraits:bool=True)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    people=[]; tenures=[]
    for expected_term,url in pages.items():
        html=fetch(url)
        actual=displayed_term(html)
        if actual is None:
            raise ValueError(f"Cannot identify displayed term: {url}")
        if actual!=expected_term:
            raise ValueError(f"Official displayed term mismatch: expected {expected_term}, got {actual}: {url}")
        rows=parse_members(html,url)
        if not rows:
            raise ValueError(f"No historical members parsed: {url}")
        for row in rows:
            pid=candidate_person_id(scope,actual,row["name"],row["portrait_source_url"])
            portrait=None
            if row["portrait_source_url"]:
                if save_portraits:
                    portrait=_mirror_portrait(root,pid,row["portrait_source_url"],stamp)
                else:
                    portrait={
                        "source_url":row["portrait_source_url"],
                        "local_path":None,
                        "checked_at":stamp,
                        "sha256":None,
                    }
            people.append({
                "person_id":pid,
                "identity_status":"candidate_unmerged",
                "name":row["name"],
                "aliases":[],
                "official_profile_url":None,
                "official_profile_code":None,
                "portrait":portrait,
                "source_detail":row["source_detail"],
                "source_url":url,
                "checked_at":stamp,
            })
            tenures.append({
                "person_id":pid,
                "council_scope":scope,
                "term":actual,
                "start_date":None,
                "end_date":None,
                "period_precision":"term_only",
                "source_url":url,
                "checked_at":stamp,
            })
    save_json(root/f"archive/people/history/{scope}_people_candidates.json",people)
    save_json(root/f"archive/people/history/{scope}_tenures.json",tenures)
    report={
        "checked_at":stamp,
        "council_scope":scope,
        "terms":sorted(pages),
        "people_candidate_rows":len(people),
        "tenure_rows":len(tenures),
        "identity_policy":"candidate_unmerged_until_evidence",
    }
    save_json(root/f"reports/{scope}-historical-members.json",report)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scope",choices=["cheongju_old_city","cheongwon_old_county"],required=True)
    p.add_argument("--no-portraits",action="store_true")
    args=p.parse_args()
    if args.scope=="cheongju_old_city":
        report=collect_static_scope(args.scope,OLD_CITY_PAGES,save_portraits=not args.no_portraits)
    else:
        report=collect_static_scope(args.scope,OLD_COUNTY_PAGES,save_portraits=not args.no_portraits)
    print(json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
