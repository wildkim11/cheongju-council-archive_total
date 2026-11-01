"""One-time inspection of discovered historical research-group official pages."""
import json,re,urllib.parse
from collect_current_members import fetch_text, BASE
from discover_historical_research_sources import parse_candidates

URLS=[
"https://council.cheongju.go.kr/content/news/notice.html?fidx=14438&pg=vv&sid=1000&page=11&opt=&sword=",
"https://council.cheongju.go.kr/content/news/notice.html?fidx=15672&pg=vv&sid=1000&page=9&opt=&sword=",
"https://council.cheongju.go.kr/content/activity/researchReport.html?fidx=17240&pg=vv&sid=1000&page=1&opt=&sword=",
"https://council.cheongju.go.kr/content/news/notice.html?fidx=17189&pg=vv&sid=1000&page=7&opt=&sword=",
"https://council.cheongju.go.kr/content/activity/researchReport.html?fidx=19753&pg=vv&sid=1000&page=1&opt=&sword=",
"https://council.cheongju.go.kr/content/activity/researchReport.html?fidx=20871&pg=vv&sid=1000&page=1&opt=&sword=",
]

def visible(raw):
    raw=re.sub(r"<script\b[\s\S]*?</script>"," ",raw,flags=re.I)
    raw=re.sub(r"<style\b[\s\S]*?</style>"," ",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",raw).strip()

def main():
    out=[]
    for url in URLS:
        html=fetch_text(url)
        text=visible(html)
        links=[]
        for href,label in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',html,flags=re.I):
            lab=visible(label)
            absolute=urllib.parse.urljoin(url,href)
            if re.search(r"\.(?:pdf|hwp|hwpx|xls|xlsx|doc|docx)(?:\?|$)",absolute,re.I) or "download" in absolute.lower() or "첨부" in lab:
                links.append({"label":lab[:160],"url":absolute})
        year=re.search(r"(20\d{2})",text)
        out.append({
            "url":url,
            "year":int(year.group(1)) if year else None,
            "text_excerpt":text[:2500],
            "attachment_links":links[:30],
            "contains_participant_keyword":("참여의원" in text or "참여 의원" in text),
            "contains_representative_keyword":("(대표)" in text or "대표의원" in text or "대표 의원" in text),
        })
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
