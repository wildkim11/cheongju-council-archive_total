"""Collect photo-activity metadata from list pages only.

No photo binaries or thumbnails are mirrored. The official detail URL is retained.
"""
from __future__ import annotations
import datetime as dt, html as html_lib, json, re, urllib.parse
from pathlib import Path
from archive_common import save_json
from collect_current_members import fetch_text
from activity_common import visible_text

ROOT=Path(__file__).resolve().parents[1]
URL="https://council.cheongju.go.kr/content/activity/photo.html?gtid=photo"

def parse_page(html:str,page_url:str)->list[dict]:
    out=[];seen=set()
    for li in re.findall(r"<li\b[^>]*>([\s\S]*?)</li>",html,flags=re.I):
        subject=re.search(
            r'<p\b[^>]*class=["\'][^"\']*\bsubject\b[^"\']*["\'][^>]*>\s*'
            r'<a\b[^>]*href=["\']([^"\']*\bfidx=(\d+)[^"\']*)["\'][^>]*>([\s\S]*?)</a>',
            li,flags=re.I,
        )
        if not subject:
            continue
        href,fidx,title_raw=subject.group(1),subject.group(2),subject.group(3)
        if fidx in seen: continue
        date_m=re.search(
            r'<p\b[^>]*class=["\'][^"\']*\bdate\b[^"\']*["\'][^>]*>\s*'
            r'(20\d{2}-\d{2}-\d{2})\s*</p>',
            li,flags=re.I,
        )
        if not date_m:
            continue
        seen.add(fidx)
        out.append({
            "source_id":fidx,
            "activity_type":"photo",
            "council_scope":"cheongju_integrated",
            "title":visible_text(title_raw),
            "date":date_m.group(1),
            "official_url":html_lib.unescape(urllib.parse.urljoin(page_url,href)),
            "binary_mirrored":False,
        })
    return out

def collect(root:Path=ROOT,max_pages:int=2000)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    rows=[];seen=set();empty=0
    for page in range(1,max_pages+1):
        page_url=f"{URL}&page={page}"
        parsed=parse_page(fetch_text(page_url),page_url)
        new=[r for r in parsed if r["source_id"] not in seen]
        for r in new:
            seen.add(r["source_id"]);r["checked_at"]=stamp;rows.append(r)
        if parsed:
            empty=0
        elif rows:
            empty+=1
            if empty>=2: break
    if not rows:
        raise ValueError("No photo activity metadata collected")
    rows.sort(key=lambda r:(r["date"],int(r["source_id"])))
    save_json(root/"archive/activities/photo_activity.json",rows)
    report={
        "checked_at":stamp,
        "records":len(rows),
        "min_date":min(r["date"] for r in rows),
        "max_date":max(r["date"] for r in rows),
        "binary_files_mirrored":0,
    }
    save_json(root/"reports/photo-activity.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(collect(),ensure_ascii=False))
