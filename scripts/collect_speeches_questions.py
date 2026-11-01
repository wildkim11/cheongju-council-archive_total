"""Collect numbered official speech/question records with full visible body text."""
from __future__ import annotations
import argparse, datetime as dt, json, re
from pathlib import Path
from archive_common import save_json
from collect_current_members import fetch_text
from activity_common import discover_links, visible_text, attachment_links, section_after_label

ROOT=Path(__file__).resolve().parents[1]
CONFIG={
    "five_minute":{
        "list_url":"https://council.cheongju.go.kr/content/activity/fiveRemark.html",
        "detail_pattern":r"fiveRemark\.html\?[^#]*\bnumber=(\d+)",
        "section_label":"5분자유발언",
        "output":"archive/activities/five_minute_speeches.json",
        "report":"reports/five-minute-speeches.json",
    },
    "city_question":{
        "list_url":"https://council.cheongju.go.kr/content/activity/question.html",
        "detail_pattern":r"question\.html\?[^#]*\bnumber=(\d+)",
        "section_label":"시정질문",
        "output":"archive/activities/city_questions.json",
        "report":"reports/city-questions.json",
    },
}

def _detail_section(text:str,label:str)->str:
    s=section_after_label(text,label)
    cuts=[]
    for pattern in (r"(?:^|\n)\s*목록\s*(?:\n|$)",r"\n\s*전체\s+\d+\s*,\s*\d+/\d+\s*페이지"):
        m=re.search(pattern,s)
        if m: cuts.append(m.start())
    if cuts: s=s[:min(cuts)].strip()
    return s

def parse_detail(html:str,row:dict,label:str)->dict:
    text=visible_text(html)
    section=_detail_section(text,label)
    lines=[re.sub(r"\s+"," ",x).strip() for x in section.splitlines() if x.strip()]
    # Expected source shape: title / member 의원 / YYYY-MM-DD / 회의록 / 영상보기 / body...
    if not lines:
        raise ValueError("Empty activity detail section")
    title=lines[0]
    speaker=None;date=None
    speaker_idx=None;date_idx=None
    for i,x in enumerate(lines[1:8],1):
        m=re.fullmatch(r"([가-힣]{2,5})\s*의원",x)
        if m and speaker is None:
            speaker=m.group(1);speaker_idx=i
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}",x) and date is None:
            date=x;date_idx=i
    if not speaker or not date:
        raise ValueError(f"Missing explicit speaker/date in {row['official_url']}")
    body_start=max(speaker_idx or 0,date_idx or 0)+1
    while body_start<len(lines) and lines[body_start] in {"회의록","영상보기"}:
        body_start+=1
    body="\n".join(lines[body_start:]).strip()
    if len(body)<30:
        raise ValueError(f"Activity body unexpectedly short: {row['official_url']}")
    return {
        **row,
        "title":title,
        "speaker_name":speaker,
        "date":date,
        "body_text":body,
        "attachments":attachment_links(html,row["official_url"]),
    }

def collect(kind:str,root:Path=ROOT,max_pages:int=500)->dict:
    if kind not in CONFIG: raise ValueError(kind)
    cfg=CONFIG[kind]
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    listed=discover_links(cfg["list_url"],cfg["detail_pattern"],max_pages=max_pages)
    rows=[]
    for row in listed:
        parsed=parse_detail(fetch_text(row["official_url"]),row,cfg["section_label"])
        parsed.update({
            "activity_type":kind,
            "council_scope":"cheongju_integrated",
            "checked_at":stamp,
        })
        rows.append(parsed)
    rows.sort(key=lambda r:(r["date"],int(r["source_id"])))
    save_json(root/cfg["output"],rows)
    report={
        "checked_at":stamp,
        "activity_type":kind,
        "records":len(rows),
        "min_date":min(r["date"] for r in rows),
        "max_date":max(r["date"] for r in rows),
        "with_body":sum(bool(r["body_text"]) for r in rows),
        "with_explicit_speaker":sum(bool(r["speaker_name"]) for r in rows),
    }
    save_json(root/cfg["report"],report)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--kind",choices=sorted(CONFIG),required=True)
    p.add_argument("--max-pages",type=int,default=500)
    a=p.parse_args()
    print(json.dumps(collect(a.kind,max_pages=a.max_pages),ensure_ascii=False))

if __name__=="__main__":
    main()
