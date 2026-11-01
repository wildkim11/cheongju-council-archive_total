"""Historical member adapters for official council pages.

Source facts only. Same-name people across terms are not automatically merged unless
an official stable identifier exists. Identity resolution is a separate, auditable step.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import html as html_lib
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


def _visible_text(raw:str)->str:
    raw=re.sub(r"<br\s*/?>"," ",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",html_lib.unescape(raw)).strip()


def _member_section(html:str)->str:
    m=re.search(
        r'<section\b[^>]*class=["\'][^"\']*\bmember\b[^"\']*["\'][^>]*>([\s\S]*?)</section>',
        html,
        flags=re.I,
    )
    if not m:
        raise ValueError("Missing official member section")
    return m.group(1)


def parse_members(html:str,source_url:str)->list[dict]:
    """Parse one official static legacy roster page.

    Both old-city and old-county pages use section.member > ul > li. The image
    alt (or strong text fallback) is the source name. Any text after the strong
    name is retained as an explicit represented-area label, not reinterpreted.
    """
    section=_member_section(html)
    blocks=re.findall(r"<li\b[^>]*>([\s\S]*?)</li>",section,flags=re.I)
    out=[];seen=set()
    for raw in blocks:
        img=re.search(
            r'<img\b[^>]*src=["\']([^"\']+)["\'][^>]*>',
            raw,
            flags=re.I,
        )
        if not img:
            continue
        img_tag=img.group(0)
        alt_match=re.search(r'alt=["\']([^"\']*)["\']',img_tag,flags=re.I)
        strong_match=re.search(r"<strong\b[^>]*>([\s\S]*?)</strong>",raw,flags=re.I)

        name=(html_lib.unescape(alt_match.group(1)).strip() if alt_match else None)
        if not name and strong_match:
            name=_visible_text(strong_match.group(1))
        if not name or not re.fullmatch(r"[가-힣]{2,5}",name):
            continue

        portrait_url=_abs(img.group(1))
        represented_area=None
        if strong_match:
            tail=raw[strong_match.end():]
            # Only visible text remaining in the same member item is retained.
            value=_visible_text(tail)
            value=re.sub(r"^[\s,·/-]+|[\s,·/-]+$","",value)
            represented_area=value or None

        key=(name,portrait_url,represented_area)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "name":name,
            "source_detail":represented_area,
            "represented_area_label":represented_area,
            "portrait_source_url":portrait_url,
            "source_url":source_url,
        })

    if not out:
        raise ValueError(f"No member rows parsed from official member section: {source_url}")
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
    people=[]; tenures=[]; represented_areas=[]
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
                "represented_area_label":row.get("represented_area_label"),
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
            if row.get("represented_area_label"):
                represented_areas.append({
                    "person_id":pid,
                    "council_scope":scope,
                    "term":actual,
                    "label":row["represented_area_label"],
                    "label_type":"official_roster_represented_area",
                    "start_date":None,
                    "end_date":None,
                    "period_precision":"term_only",
                    "source_url":url,
                    "checked_at":stamp,
                })
    save_json(root/f"archive/people/history/{scope}_people_candidates.json",people)
    save_json(root/f"archive/people/history/{scope}_tenures.json",tenures)
    save_json(root/f"archive/people/history/{scope}_represented_areas.json",represented_areas)
    report={
        "checked_at":stamp,
        "council_scope":scope,
        "terms":sorted(pages),
        "people_candidate_rows":len(people),
        "tenure_rows":len(tenures),
        "represented_area_rows":len(represented_areas),
        "by_term":{
            str(term):sum(1 for row in tenures if row["term"]==term)
            for term in sorted(pages)
        },
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
