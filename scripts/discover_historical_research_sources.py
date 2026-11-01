"""Discover official historical research-group source pages.

Discovery is non-promoting. It records official notice/report candidates only.
Full roster promotion is handled separately.
"""
from __future__ import annotations
import datetime as dt
import json,re,urllib.parse
from pathlib import Path
from archive_common import save_json
from collect_current_members import BASE, fetch_text

ROOT=Path(__file__).resolve().parents[1]
NOTICE=f"{BASE}/content/news/notice.html"
REPORT=f"{BASE}/content/activity/researchReport.html"

KEYWORDS=(
    "의원 연구단체 구성 현황",
    "의원연구단체 구성 현황",
    "의원 연구단체 연구활동보고서",
    "의원연구단체 연구활동보고서",
)

def _visible(raw:str)->str:
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",raw).strip()

def parse_candidates(html:str,base_url:str)->list[dict]:
    out=[];seen=set()
    for m in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']*[?&]fidx=(\d+)[^"\']*)["\'][^>]*>([\s\S]*?)</a>',
        html,flags=re.I,
    ):
        href,fidx,inner=m.group(1),m.group(2),m.group(3)
        title=_visible(inner)
        if not title or not any(k in title for k in KEYWORDS):
            continue
        ym=re.search(r"(20\d{2})",title)
        key=(fidx,title)
        if key in seen: continue
        seen.add(key)
        out.append({
            "fidx":int(fidx),
            "year":int(ym.group(1)) if ym else None,
            "title":title,
            "official_url":urllib.parse.urljoin(base_url,href),
            "source_family":"notice" if "notice.html" in base_url else "research_report",
        })
    return out

def discover(max_pages:int=30,root:Path=ROOT)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    found={}
    pages_checked={}
    for family,base in (("notice",NOTICE),("research_report",REPORT)):
        pages_checked[family]=0
        for page in range(1,max_pages+1):
            sep="&" if "?" in base else "?"
            url=f"{base}{sep}page={page}"
            html=fetch_text(url);pages_checked[family]+=1
            rows=parse_candidates(html,base)
            for row in rows:
                found[(row["source_family"],row["fidx"])]=row
            # Stop conservatively after two consecutive empty pages beyond page 2.
            if page>2 and not rows:
                next_html=fetch_text(f"{base}{sep}page={page+1}")
                pages_checked[family]+=1
                next_rows=parse_candidates(next_html,base)
                for row in next_rows:
                    found[(row["source_family"],row["fidx"])]=row
                if not next_rows:
                    break
                page+=1
    rows=sorted(found.values(),key=lambda r:((r.get("year") or 0),r["source_family"],r["fidx"]))
    report={
        "checked_at":stamp,
        "candidate_count":len(rows),
        "pages_checked":pages_checked,
        "candidates":rows,
    }
    save_json(root/"reports/historical-research-source-candidates.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(discover(),ensure_ascii=False))
