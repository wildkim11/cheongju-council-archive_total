"""Collect metadata and official attachment links for historical research-group sources.

PDF/HWP binaries are not mirrored. This collector records official source pages
and attachment identifiers so later roster verification can inspect them transiently.
"""
from __future__ import annotations
import datetime as dt
import html as html_lib
import json,re,urllib.parse
from pathlib import Path

from archive_common import save_json
from collect_current_members import fetch_text

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/"config/historical_research_sources.json"

def _visible(raw:str)->str:
    raw=re.sub(r"<script\b[\s\S]*?</script>"," ",raw,flags=re.I)
    raw=re.sub(r"<style\b[\s\S]*?</style>"," ",raw,flags=re.I)
    raw=re.sub(r"<br\s*/?>"," ",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",html_lib.unescape(raw)).strip()

def attachment_links(html:str,page_url:str)->list[dict]:
    out=[];seen=set()
    for m in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
        html,flags=re.I,
    ):
        href,label_raw=m.group(1),m.group(2)
        label=_visible(label_raw)
        absolute=html_lib.unescape(urllib.parse.urljoin(page_url,href))
        q=urllib.parse.parse_qs(urllib.parse.urlsplit(absolute).query)
        if "gtb_download.php" not in absolute and not re.search(
            r"\.(?:pdf|hwp|hwpx|xls|xlsx|doc|docx)(?:\?|$)",absolute,re.I
        ):
            continue
        fid=(q.get("fid") or [None])[0]
        gtid=(q.get("gtid") or [None])[0]
        key=(absolute,label)
        if key in seen: continue
        seen.add(key)
        ext=None
        em=re.search(r"\.([A-Za-z0-9]{2,5})(?:\s|$)",label)
        if em: ext=em.group(1).lower()
        out.append({
            "title":label or None,
            "official_url":absolute,
            "official_attachment_id":fid,
            "official_attachment_group":gtid,
            "file_type":ext,
        })
    return out

def _group_name_from_attachment(title:str|None)->str|None:
    if not title: return None
    value=re.sub(r"\.pdf$","",title,flags=re.I).strip()
    # Parenthetical report filenames usually contain the group name.
    m=re.search(r"\(([^()]+)\)\s*$",value)
    if m:
        return re.sub(r"\s+"," ",m.group(1)).strip()
    value=re.sub(r"^\d{4}년\s*의원\s*연구단체\s*연구활동\s*보고서","",value)
    value=re.sub(r"^(?:연구활동결과보고|연구활동보고서|활동결과보고|연구활동결보고서)","",value)
    return value.strip(" -_()") or None

def _registered_groups(text:str)->list[str]:
    m=re.search(r"등록단체\s*:\s*\d+개\s*단체\s*\(([^)]*)\)",text)
    if not m: return []
    return [
        re.sub(r"\s+"," ",x).strip()
        for x in re.split(r"\s*,\s*",m.group(1))
        if x.strip()
    ]

def collect(root:Path=ROOT)->dict:
    cfg=json.loads(REGISTRY.read_text(encoding="utf-8"))
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    pages=[];attachments=[]
    for src in cfg["sources"]:
        html=fetch_text(src["official_url"])
        text=_visible(html)
        links=attachment_links(html,src["official_url"])
        page={
            **src,
            "checked_at":stamp,
            "attachment_count":len(links),
            "registered_group_names":_registered_groups(text),
            "contains_participant_keyword":("참여의원" in text or "참여 의원" in text),
            "contains_representative_keyword":(
                "(대표)" in text or "대표의원" in text or "대표 의원" in text
            ),
        }
        pages.append(page)
        for item in links:
            attachments.append({
                "parent_type":"research_source",
                "parent_id":src["source_id"],
                "year":src["year"],
                "source_family":src["source_family"],
                **item,
                "group_name_candidate":_group_name_from_attachment(item.get("title")),
                "first_seen_at":stamp,
                "last_checked_at":stamp,
            })

    save_json(root/"archive/research_groups/historical_source_pages.json",pages)
    save_json(root/"archive/research_groups/historical_attachments.json",attachments)
    report={
        "checked_at":stamp,
        "source_pages":len(pages),
        "attachments":len(attachments),
        "pages_with_html_full_roster":sum(
            p["contains_participant_keyword"] and p["contains_representative_keyword"]
            for p in pages
        ),
        "attachment_verification_required":sum(
            p.get("source_status")=="attachment_verification_required" for p in pages
        ),
        "by_year":{
            str(y):sum(p["year"]==y for p in pages)
            for y in sorted({p["year"] for p in pages})
        },
    }
    save_json(root/"reports/historical-research-metadata.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(collect(),ensure_ascii=False))
