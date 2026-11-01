"""One-time inspection of a written-question detail page."""
import json,re,html as html_lib,urllib.parse
from collect_current_members import fetch_text
from activity_common import visible_text, attachment_links

URL="https://council.cheongju.go.kr/content/activity/questionLetter.html?pg=vv&number=29&page=1&sword="

def main():
    html=fetch_text(URL)
    text=visible_text(html)
    i=text.rfind("서면질문")
    section=text[i:i+7000] if i>=0 else text[:7000]
    links=[]
    for href,label in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',html,flags=re.I):
        lab=visible_text(label)
        full=html_lib.unescape(urllib.parse.urljoin(URL,href))
        if "paper_down" in full or "download" in full or "질문" in lab or "답변" in lab:
            links.append({"label":lab,"url":full})
    print(json.dumps({"section":section,"links":links[:30],"attachments":attachment_links(html,URL)},ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
