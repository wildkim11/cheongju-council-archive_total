"""Collect official fidx-based activity boards as source facts."""
from __future__ import annotations
import argparse, datetime as dt, json, re
from pathlib import Path
from archive_common import save_json
from collect_current_members import fetch_text
from activity_common import discover_links, visible_text, attachment_links

ROOT=Path(__file__).resolve().parents[1]
CONFIG={
    "suggestion_resolution":{
        "list_url":"https://council.cheongju.go.kr/content/activity/suggestion.html",
        "detail_pattern":r"suggestion\.html\?[^#]*\bfidx=(\d+)",
        "section_label":"건의/결의문",
        "output":"archive/activities/suggestions_resolutions.json",
        "report":"reports/suggestions-resolutions.json",
        "body_expected":True,
    },
    "press":{
        "list_url":"https://council.cheongju.go.kr/content/news/bodo.html",
        "detail_pattern":r"bodo\.html\?[^#]*\bfidx=(\d+)",
        "section_label":"보도자료",
        "output":"archive/activities/press.json",
        "report":"reports/press.json",
        "body_expected":True,
    },
    "debate":{
        "list_url":"https://council.cheongju.go.kr/content/activity/debate.html",
        "detail_pattern":r"debate\.html\?[^#]*\bfidx=(\d+)",
        "section_label":"토론회",
        "output":"archive/activities/debates.json",
        "report":"reports/debates.json",
        "body_expected":False,
    },
    "photo":{
        "list_url":"https://council.cheongju.go.kr/content/activity/photo.html?gtid=photo",
        "detail_pattern":r"photo\.html\?[^#]*\bfidx=(\d+)",
        "section_label":"포토의정",
        "output":"archive/activities/photo_activity.json",
        "report":"reports/photo-activity.json",
        "body_expected":False,
    },
}

def _section(text:str,label:str)->str:
    marker=f"\n {label}\n"
    i=text.rfind(marker)
    if i<0: i=text.rfind(label)
    if i<0: raise ValueError(f"Missing section label: {label}")
    s=text[i+len(label):].strip()
    cuts=[]
    for p in (
        r"\n\s*목록\s*\n",
        r"\n\s*전체\s+\d+\s*,\s*\d+/\d+\s*페이지",
        r"\n\s*게시물검색\s*\n",
    ):
        m=re.search(p,s)
        if m: cuts.append(m.start())
    return s[:min(cuts)].strip() if cuts else s

def _date_index(lines:list[str])->tuple[int|None,str|None]:
    for i,x in enumerate(lines[:12]):
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}",x):
            return i,x
    return None,None

def parse_detail(html:str,row:dict,cfg:dict)->dict:
    text=visible_text(html)
    section=_section(text,cfg["section_label"])
    lines=[re.sub(r"\s+"," ",x).strip() for x in section.splitlines() if x.strip()]
    if not lines: raise ValueError(f"Empty detail section: {row['official_url']}")
    title=lines[0]
    date_i,date=_date_index(lines)
    if not date:
        raise ValueError(f"No explicit date: {row['official_url']}")

    # The source usually prints an author/committee line immediately before date.
    author=None
    if date_i and date_i>=2:
        candidate=lines[date_i-1]
        if not candidate.startswith("조회수"):
            author=candidate

    attachments=attachment_links(html,row["official_url"])
    attachment_titles={x["title"] for x in attachments if x.get("title")}
    body_lines=[]
    for x in lines[(date_i or 0)+1:]:
        if x.startswith("조회수"): continue
        if x in attachment_titles: continue
        if x in {"원본 사진받기","회의록","영상보기"}: continue
        body_lines.append(x)
    body="\n".join(body_lines).strip()

    if cfg["body_expected"] and len(body)<20:
        raise ValueError(f"Expected body text missing: {row['official_url']}")

    return {
        **row,
        "activity_type":next(k for k,v in CONFIG.items() if v is cfg),
        "council_scope":"cheongju_integrated",
        "title":title,
        "author_label":author,
        "date":date,
        "body_text":body or None,
        "attachments":attachments,
    }

def collect(kind:str,root:Path=ROOT,max_pages:int=1000)->dict:
    if kind not in CONFIG: raise ValueError(kind)
    cfg=CONFIG[kind]
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    listed=discover_links(cfg["list_url"],cfg["detail_pattern"],max_pages=max_pages)
    rows=[]
    for row in listed:
        parsed=parse_detail(fetch_text(row["official_url"]),row,cfg)
        parsed["checked_at"]=stamp
        rows.append(parsed)
    rows.sort(key=lambda r:(r["date"],int(r["source_id"])))
    save_json(root/cfg["output"],rows)
    report={
        "checked_at":stamp,
        "activity_type":kind,
        "records":len(rows),
        "min_date":min(r["date"] for r in rows),
        "max_date":max(r["date"] for r in rows),
        "with_body":sum(bool(r.get("body_text")) for r in rows),
        "attachment_links":sum(len(r.get("attachments") or []) for r in rows),
    }
    save_json(root/cfg["report"],report)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--kind",choices=sorted(CONFIG),required=True)
    p.add_argument("--max-pages",type=int,default=1000)
    a=p.parse_args()
    print(json.dumps(collect(a.kind,max_pages=a.max_pages),ensure_ascii=False))

if __name__=="__main__":
    main()
