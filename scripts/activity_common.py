"""Shared helpers for official council activity-board collectors."""
from __future__ import annotations
import html as html_lib
import re, urllib.parse
from collect_current_members import fetch_text

BASE="https://council.cheongju.go.kr"

def visible_text(raw:str)->str:
    raw=re.sub(r"<!--[\s\S]*?-->"," ",raw)
    raw=raw.replace("-->"," ")
    raw=re.sub(r"<script\b[\s\S]*?</script>"," ",raw,flags=re.I)
    raw=re.sub(r"<style\b[\s\S]*?</style>"," ",raw,flags=re.I)
    raw=re.sub(r"<br\s*/?>","\n",raw,flags=re.I)
    raw=re.sub(r"</(?:p|div|li|tr|td|th|dt|dd|h[1-6]|article|section)>","\n",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    raw=html_lib.unescape(raw)
    raw=re.sub(r"[ \t]+"," ",raw)
    return re.sub(r"\n\s*\n+","\n",raw).strip()

def attachment_links(html:str,page_url:str)->list[dict]:
    out=[];seen=set()
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',html,flags=re.I):
        href,label_raw=m.group(1),m.group(2)
        label=visible_text(label_raw)
        url=html_lib.unescape(urllib.parse.urljoin(page_url,href))
        if "gtb_download.php" not in url and "download" not in url.lower() and not re.search(
            r"\.(?:pdf|hwp|hwpx|xls|xlsx|doc|docx|zip)(?:\?|$)",url,re.I
        ):
            continue
        q=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        key=(url,label)
        if key in seen: continue
        seen.add(key)
        ext=None
        mext=re.search(r"\.([A-Za-z0-9]{2,5})\s*$",label)
        if mext: ext=mext.group(1).lower()
        out.append({
            "title":label or None,
            "official_url":url,
            "official_attachment_id":(q.get("fid") or [None])[0],
            "official_attachment_group":(q.get("gtid") or [None])[0],
            "file_type":ext,
        })
    return out

def discover_links(list_url:str,pattern:str,id_group:int=1,max_pages:int=500)->list[dict]:
    """Discover unique detail URLs across paginated official board pages.

    Stops after two consecutive pages with no detail links once at least one page
    has yielded results. This is a list-structure stop condition, not a keyword
    stop condition.
    """
    out=[];seen=set();empty=0;found_any=False
    rx=re.compile(pattern,re.I)
    for page in range(1,max_pages+1):
        sep="&" if "?" in list_url else "?"
        url=f"{list_url}{sep}page={page}"
        html=fetch_text(url)
        page_rows=[]
        for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',html,flags=re.I):
            href,label=m.group(1),m.group(2)
            full=urllib.parse.urljoin(url,html_lib.unescape(href))
            mm=rx.search(full)
            if not mm: continue
            source_id=mm.group(id_group)
            if source_id in seen: continue
            seen.add(source_id);found_any=True
            page_rows.append({
                "source_id":source_id,
                "title_list":visible_text(label),
                "official_url":full,
                "list_page":page,
                "list_source_url":url,
            })
        out.extend(page_rows)
        if page_rows:
            empty=0
        elif found_any:
            empty+=1
            if empty>=2: break
    if not out:
        raise ValueError(f"No detail links discovered: {list_url}")
    return out

def date_candidates(text:str)->list[str]:
    out=[]
    patterns=[
        r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})",
        r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일",
    ]
    import datetime as dt
    for p in patterns:
        for y,m,d in re.findall(p,text):
            try:
                iso=dt.date(int(y),int(m),int(d)).isoformat()
            except ValueError:
                continue
            if iso not in out: out.append(iso)
    return out

def first_labeled_value(text:str,labels:list[str])->str|None:
    """Best-effort source-text extraction for explicit labels only."""
    flat=re.sub(r"\s+"," ",text)
    for label in labels:
        m=re.search(rf"{re.escape(label)}\s*[:：]?\s*(.+?)(?=\s+(?:작성자|등록일|조회수|의원명|발언자|질문자|제목|회기|일시|일자|첨부파일|답변|본문)\s*[:：]?|$)",flat)
        if m:
            value=m.group(1).strip()
            if value: return value
    return None


def section_after_label(text:str,label:str)->str:
    """Return content after the last line whose full visible text equals label."""
    lines=[x.strip() for x in text.splitlines()]
    positions=[i for i,x in enumerate(lines) if x==label]
    if not positions:
        raise ValueError(f"Missing section label line: {label}")
    return "\n".join(lines[positions[-1]+1:]).strip()
