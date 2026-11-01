"""Discover candidate historical committee-composition sources from official boards.

Discovery is non-promoting: it outputs candidates only. Human/reviewed registry
promotion is separate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import urllib.parse
from pathlib import Path

from archive_common import save_json
from collect_current_members import BASE, fetch_text

ROOT=Path(__file__).resolve().parents[1]

BOARD_SEEDS={
    "standing":f"{BASE}/content/committee/coActivity_C101.html",
    "budget_special":f"{BASE}/content/committee/coActivity_G100.html",
    "ethics_special":f"{BASE}/content/committee/coActivity_G140.html",
}
KEYWORDS=(
    "상임위원회 구성",
    "상임위원장단 선출",
    "예산결산특별위원장",
    "예결",
    "윤리특별위원장",
    "윤리특위",
    "특별위원회 구성",
    "특별위원장",
)


def _visible(raw:str)->str:
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",raw).strip()


def parse_board_candidates(html:str,board_name:str,board_url:str)->list[dict]:
    out=[]
    seen=set()
    for m in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']*[?&]fidx=(\d+)[^"\']*)["\'][^>]*>([\s\S]*?)</a>',
        html,
        flags=re.I,
    ):
        href,fidx,inner=m.group(1),m.group(2),m.group(3)
        title=_visible(inner)
        if not title or not any(k in title for k in KEYWORDS):
            continue
        key=(fidx,title)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "fidx":int(fidx),
            "title":title,
            "board":board_name,
            "official_url":urllib.parse.urljoin(board_url,href),
        })
    return out


def discover(max_pages:int=10,root:Path=ROOT)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    candidates={}
    pages_checked={}
    for board_name,base_url in BOARD_SEEDS.items():
        pages_checked[board_name]=0
        for page in range(1,max_pages+1):
            sep="&" if "?" in base_url else "?"
            url=f"{base_url}{sep}page={page}"
            html=fetch_text(url)
            pages_checked[board_name]+=1
            rows=parse_board_candidates(html,board_name,base_url)
            for row in rows:
                key=str(row["fidx"])
                prior=candidates.get(key)
                if prior:
                    boards=set(prior["boards"]);boards.add(board_name)
                    prior["boards"]=sorted(boards)
                else:
                    candidates[key]={
                        "fidx":row["fidx"],
                        "title":row["title"],
                        "boards":[board_name],
                        "official_url":row["official_url"],
                    }

            # Official board pagination ends when current page is beyond available list.
            if page>1 and "게시판 목록" in _visible(html) and not re.search(
                rf"[?&]page={page+1}(?:[&#\"'])",html
            ):
                # Keep one conservative extra page only if it still yielded candidates.
                if not rows:
                    break

    rows=sorted(candidates.values(),key=lambda r:r["fidx"])
    report={
        "checked_at":stamp,
        "candidate_count":len(rows),
        "pages_checked":pages_checked,
        "candidates":rows,
    }
    save_json(root/"reports/historical-committee-source-candidates.json",report)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--max-pages",type=int,default=10)
    args=p.parse_args()
    print(json.dumps(discover(args.max_pages),ensure_ascii=False))


if __name__=="__main__":
    main()
