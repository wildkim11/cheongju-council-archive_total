"""Collect official written-question rows and question/answer file links."""
from __future__ import annotations
import datetime as dt, html as html_lib, json, re, urllib.parse
from pathlib import Path
from archive_common import save_json
from collect_current_members import fetch_text
from activity_common import visible_text

ROOT=Path(__file__).resolve().parents[1]
URL="https://council.cheongju.go.kr/content/activity/questionLetter.html"

def _file_link(raw:str,label_hint:str,page_url:str)->str|None:
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',raw,flags=re.I):
        label=visible_text(m.group(2))
        if label_hint in label:
            return html_lib.unescape(urllib.parse.urljoin(page_url,m.group(1)))
    return None

def parse_page(html:str,page_url:str)->list[dict]:
    out=[];seen=set()
    for tr in re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>",html,flags=re.I):
        cells=[visible_text(x) for x in re.findall(r"<td\b[^>]*>([\s\S]*?)</td>",tr,flags=re.I)]
        if len(cells)<4 or not re.fullmatch(r"\d+",cells[0] or ""):
            continue
        source_id=cells[0]
        if source_id in seen: continue
        seen.add(source_id)
        date=cells[1] if re.fullmatch(r"20\d{2}-\d{2}-\d{2}",cells[1] or "") else None
        member=re.sub(r"\s+","",cells[2] or "")
        # content cell may contain comment residue; visible text is canonical source title.
        title=cells[3].strip()
        if not date or not re.fullmatch(r"[가-힣]{2,5}",member) or not title:
            continue
        detail_url=_file_link(tr,"질문파일",page_url)
        answer_list_url=_file_link(tr,"답변파일",page_url)
        record_number=_record_number(detail_url)
        out.append({
            "source_id":record_number or source_id,
            "list_number":source_id,
            "activity_type":"written_question",
            "council_scope":"cheongju_integrated",
            "date":date,
            "speaker_name":member,
            "title":title,
            "detail_url":detail_url,
            "answer_file_url_list":answer_list_url,
            "minutes_url":_file_link(tr,"회의록",page_url),
            "list_source_url":page_url,
        })
    return out

def collect(root:Path=ROOT,max_pages:int=100)->dict:
    stamp=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    rows=[];seen=set();empty=0
    for page in range(1,max_pages+1):
        page_url=f"{URL}?page={page}"
        parsed=parse_page(fetch_text(page_url),page_url)
        new=[r for r in parsed if r["source_id"] not in seen]
        for r in new:
            seen.add(r["source_id"])
            if r.get("detail_url"):
                files=parse_detail_files(fetch_text(r["detail_url"]),r["detail_url"])
                r.update(files)
            else:
                r["question_file_url"]=None
                r["answer_file_url"]=r.get("answer_file_url_list")
            if not r.get("answer_file_url"):
                r["answer_file_url"]=r.get("answer_file_url_list")
            r["checked_at"]=stamp
            rows.append(r)
        if parsed:
            empty=0
        elif rows:
            empty+=1
            if empty>=2: break
    if not rows: raise ValueError("No written questions collected")
    rows.sort(key=lambda r:(r["date"],int(r["source_id"])))
    save_json(root/"archive/activities/written_questions.json",rows)
    report={
        "checked_at":stamp,
        "records":len(rows),
        "min_date":min(r["date"] for r in rows),
        "max_date":max(r["date"] for r in rows),
        "question_files":sum(bool(r["question_file_url"]) for r in rows),
        "answer_files":sum(bool(r["answer_file_url"]) for r in rows),
    }
    save_json(root/"reports/written-questions.json",report)
    return report

if __name__=="__main__":
    print(json.dumps(collect(),ensure_ascii=False))
