"""Collect integrated-council historical member rosters (terms 1-3).

The official page uses a POST search form with CSRF fields. This collector keeps
source facts conservative: exact dates only when explicitly printed; same-name
records are not merged without an official stable profile code.
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.cookiejar
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
URL=f"{BASE}/content/member/integrationCheongju.html"
COUNCIL_SCOPE="cheongju_integrated"
HISTORICAL_TERMS=(1,2,3)

TLS=ssl.create_default_context()
TLS.minimum_version=ssl.TLSVersion.TLSv1_2


class Session:
    def __init__(self):
        self.cookies=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.HTTPSHandler(context=TLS),
        )

    def request(self,url:str,data:dict|None=None)->tuple[bytes,str]:
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!="https" or parsed.netloc!="council.cheongju.go.kr":
            raise ValueError("Unexpected source host")
        body=None if data is None else urllib.parse.urlencode(data).encode()
        req=urllib.request.Request(
            url,
            data=body,
            headers={
                "User-Agent":"CheongjuCouncilArchive/0.1",
                "Content-Type":"application/x-www-form-urlencoded",
            },
            method="GET" if body is None else "POST",
        )
        with self.opener.open(req,timeout=40) as resp:
            if resp.status!=200:
                raise ValueError(f"Official source HTTP {resp.status}")
            return resp.read(),resp.headers.get_content_type()

    def text(self,url:str,data:dict|None=None)->str:
        raw,_=self.request(url,data)
        return raw.decode("utf-8-sig")


def _hidden(html:str,name:str)->str:
    pattern=rf'<input\b[^>]*name=["\']{re.escape(name)}["\'][^>]*>'
    m=re.search(pattern,html,flags=re.I)
    if not m:
        # Attribute order can vary.
        for tag in re.findall(r"<input\b[^>]*>",html,flags=re.I):
            n=re.search(r'name=["\']?([^"\'\s>]+)',tag,flags=re.I)
            if not n or n.group(1)!=name:
                continue
            v=re.search(r'value=["\']([^"\']*)',tag,flags=re.I)
            if v:
                return v.group(1)
        raise ValueError(f"Missing hidden field: {name}")
    v=re.search(r'value=["\']([^"\']*)',m.group(0),flags=re.I)
    if not v:
        raise ValueError(f"Missing hidden value: {name}")
    return v.group(1)


def fetch_term_html(term:int,session:Session|None=None)->str:
    if term not in HISTORICAL_TERMS and term!=4:
        raise ValueError("Unsupported integrated term")
    s=session or Session()
    base=s.text(URL)
    payload={
        "CSRFToken":_hidden(base,"CSRFToken"),
        "Anti-CSRF":_hidden(base,"Anti-CSRF"),
        "daesu":str(term),
        "sname":"",
    }
    return s.text(URL,payload)


class MemberListParser(HTMLParser):
    VOID={"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}

    def __init__(self):
        super().__init__()
        self.depth=0
        self.current=None
        self.blocks=[]

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=="li" and self.current is None:
            self.current={"depth":self.depth,"text":[],"links":[],"images":[]}
        if self.current is not None:
            if tag=="a" and attrs.get("href"):
                self.current["links"].append(attrs["href"])
            if tag=="img" and attrs.get("src"):
                self.current["images"].append({"src":attrs["src"],"alt":attrs.get("alt","")})
        if tag not in self.VOID:
            self.depth+=1

    def handle_endtag(self,tag):
        if tag not in self.VOID:
            self.depth=max(0,self.depth-1)
        if tag=="li" and self.current is not None and self.depth==self.current["depth"]:
            self.blocks.append(self.current)
            self.current=None

    def handle_data(self,data):
        if self.current is not None and data.strip():
            self.current["text"].append(data.strip())


def _absolute(url:str)->str:
    return urllib.parse.urljoin(BASE+"/",url)


def _iso_date(y:str,m:str,d:str)->str:
    return dt.date(int(y),int(m),int(d)).isoformat()


def _explicit_term_dates(text:str)->tuple[str|None,str|None]:
    m=re.search(
        r"임기\s*:\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?"
        r"\s*~\s*(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?",
        text,
    )
    if not m:
        return None,None
    return _iso_date(*m.groups()[:3]),_iso_date(*m.groups()[3:])


def _visible_text(raw:str)->str:
    raw=re.sub(r"<br\s*/?>"," ",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",html_lib.unescape(raw)).strip()


def _source_identity(href:str)->tuple[str|None,str|None]:
    query=urllib.parse.parse_qs(urllib.parse.urlsplit(_absolute(href)).query)
    if query.get("f_code"):
        return "f_code",query["f_code"][0]
    if query.get("mcode"):
        return "mcode",query["mcode"][0]
    return None,None


def parse_term_members(html:str,expected_term:int)->list[dict]:
    rows=[]
    seen=set()
    blocks=re.findall(r"<li\b[^>]*>([\s\S]*?)</li>",html,flags=re.I)
    for raw in blocks:
        if "memberProfile.html" not in raw and "f_code=" not in raw:
            continue
        href_match=re.search(r'href=["\']([^"\']+)["\']',raw,flags=re.I)
        if not href_match:
            continue
        href=href_match.group(1)
        profile_url=_absolute(href)
        query=urllib.parse.parse_qs(urllib.parse.urlsplit(profile_url).query)
        if query.get("daesu") and query["daesu"][0].isdigit():
            if int(query["daesu"][0])!=expected_term:
                continue

        text=_visible_text(raw)
        m=re.search(
            r"([가-힣]{2,5})\s*\(\s*(\d+)\s*대\s*:\s*([^)]*)\)",
            text,
        )
        if not m:
            continue
        name=m.group(1)
        term=int(m.group(2))
        if term!=expected_term:
            continue
        district=re.sub(r"\s+"," ",m.group(3)).strip() or None
        start_date,end_date=_explicit_term_dates(text)

        code_type,code=_source_identity(href)
        image_match=re.search(r'<img\b[^>]*src=["\']([^"\']+)["\']',raw,flags=re.I)
        portrait_url=_absolute(image_match.group(1)) if image_match else None

        key=(term,name,code_type,code,district,start_date,end_date)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "name":name,
            "term":term,
            "district":district,
            "start_date":start_date,
            "end_date":end_date,
            "official_profile_code":code,
            "official_profile_code_type":code_type,
            "official_profile_url":profile_url,
            "portrait_source_url":portrait_url,
            "source_url":URL,
        })
    if not rows:
        raise ValueError(f"No integrated historical members parsed for term {expected_term}")
    return rows


def _candidate_person_id(row:dict)->str:
    basis=(
        f"{COUNCIL_SCOPE}|{row['term']}|{row['name']}|"
        f"{row.get('official_profile_code_type') or ''}|"
        f"{row.get('official_profile_code') or ''}|"
        f"{row.get('district') or ''}|{row.get('portrait_source_url') or ''}"
    ).encode("utf-8")
    return "person-candidate-"+sha256_bytes(basis)[:16]


def person_id(row:dict)->str:
    code=row.get("official_profile_code")
    code_type=row.get("official_profile_code_type")
    # f_code is the stable current member-home identifier. Historical mcode is
    # scoped by daesu and must not be assumed to identify the same person across terms.
    if code and code_type=="f_code":
        return "person-fcode-"+re.sub(r"[^A-Za-z0-9_-]","_",code)
    return _candidate_person_id(row)


def _portrait_extension(content_type:str,url:str)->str:
    mapping={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}
    if content_type in mapping:
        return mapping[content_type]
    suffix=Path(urllib.parse.urlsplit(url).path).suffix.lower()
    return suffix if suffix in {".jpg",".jpeg",".png",".webp"} else ".img"


def collect(root:Path=ROOT,save_portraits:bool=True)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    session=Session()
    all_rows=[]
    for term in HISTORICAL_TERMS:
        html=fetch_term_html(term,session)
        all_rows.extend(parse_term_members(html,term))

    people_by_id={}
    tenures=[]
    districts=[]
    for row in all_rows:
        pid=person_id(row)
        portrait=None
        if row.get("portrait_source_url"):
            if save_portraits:
                raw,ctype=session.request(row["portrait_source_url"])
                ext=_portrait_extension(ctype,row["portrait_source_url"])
                local_path=f"archive/people/portraits/{pid}{ext}"
                path=root/local_path
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(raw)
                portrait={
                    "source_url":row["portrait_source_url"],
                    "local_path":local_path,
                    "checked_at":stamp,
                    "sha256":sha256_bytes(raw),
                }
            else:
                portrait={
                    "source_url":row["portrait_source_url"],
                    "local_path":None,
                    "checked_at":stamp,
                    "sha256":None,
                }

        prior=people_by_id.get(pid)
        person={
            "person_id":pid,
            "identity_status":"official_fcode" if row.get("official_profile_code_type")=="f_code" else "candidate_unmerged",
            "name":row["name"],
            "aliases":[],
            "official_profile_url":row.get("official_profile_url"),
            "official_profile_code":row.get("official_profile_code"),
            "official_profile_code_type":row.get("official_profile_code_type"),
            "portrait":portrait or (prior.get("portrait") if prior else None),
            "source_url":URL,
            "checked_at":stamp,
        }
        people_by_id[pid]=person

        precision="exact_date" if row.get("start_date") and row.get("end_date") else "term_only"
        tenures.append({
            "person_id":pid,
            "council_scope":COUNCIL_SCOPE,
            "term":row["term"],
            "start_date":row.get("start_date"),
            "end_date":row.get("end_date"),
            "period_precision":precision,
            "source_url":URL,
            "checked_at":stamp,
        })
        if row.get("district"):
            districts.append({
                "person_id":pid,
                "council_scope":COUNCIL_SCOPE,
                "term":row["term"],
                "membership_type":"district",
                "label":row["district"],
                "role":None,
                "start_date":row.get("start_date"),
                "end_date":row.get("end_date"),
                "period_precision":precision,
                "source_url":URL,
                "checked_at":stamp,
            })

    people=sorted(people_by_id.values(),key=lambda r:(r["name"],r["person_id"]))
    tenures.sort(key=lambda r:(r["term"],r["person_id"]))
    districts.sort(key=lambda r:(r["term"],r["person_id"]))

    save_json(root/"archive/people/history/cheongju_integrated_people.json",people)
    save_json(root/"archive/people/history/cheongju_integrated_tenures.json",tenures)
    save_json(root/"archive/people/history/cheongju_integrated_district_memberships.json",districts)

    report={
        "checked_at":stamp,
        "council_scope":COUNCIL_SCOPE,
        "terms":list(HISTORICAL_TERMS),
        "roster_rows":len(all_rows),
        "unique_people_rows":len(people),
        "tenure_rows":len(tenures),
        "district_rows":len(districts),
        "official_fcode_people":sum(p["identity_status"]=="official_fcode" for p in people),
        "historical_mcode_rows":sum(
            r.get("official_profile_code_type")=="mcode" for r in all_rows
        ),
        "candidate_unmerged_people":sum(p["identity_status"]=="candidate_unmerged" for p in people),
    }
    save_json(root/"reports/cheongju_integrated-historical-members.json",report)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--no-portraits",action="store_true")
    args=p.parse_args()
    print(json.dumps(collect(save_portraits=not args.no_portraits),ensure_ascii=False))


if __name__=="__main__":
    main()
