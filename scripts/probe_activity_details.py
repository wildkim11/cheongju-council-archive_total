"""One-time live inspection of official activity detail pages."""
import json,re,html as html_lib,urllib.parse
from collect_current_members import fetch_text

SAMPLES={
 "city_question":"https://council.cheongju.go.kr/content/activity/question.html?pg=vv&number=87&page=1&sword=&ssid=",
 "five_minute":"https://council.cheongju.go.kr/content/activity/fiveRemark.html?pg=vv&number=607&page=1&sword=&ssid=",
 "written_question":"https://council.cheongju.go.kr/content/activity/questionLetter.html",
 "suggestion":"https://council.cheongju.go.kr/content/activity/suggestion.html",
 "press":"https://council.cheongju.go.kr/content/news/bodo.html?fidx=22047&pg=vv&sid=1000&page=1&opt=&sword=",
 "debate":"https://council.cheongju.go.kr/content/activity/debate.html?fidx=19642&pg=vv&sid=1000&page=1&opt=&sword=",
 "photo":"https://council.cheongju.go.kr/content/activity/photo.html?gtid=photo&pg=vv&sid=1000&page=1&fidx=6644&opt=&sword=",
}
def visible(raw):
    raw=re.sub(r"<script\b[\s\S]*?</script>"," ",raw,flags=re.I)
    raw=re.sub(r"<style\b[\s\S]*?</style>"," ",raw,flags=re.I)
    raw=re.sub(r"<br\s*/?>","\n",raw,flags=re.I)
    raw=re.sub(r"</(?:p|div|li|tr|td|th|dt|dd|h[1-6])>","\n",raw,flags=re.I)
    raw=re.sub(r"<[^>]+>"," ",raw)
    raw=html_lib.unescape(raw)
    raw=re.sub(r"[ \t]+"," ",raw)
    return re.sub(r"\n\s*\n+","\n",raw).strip()
def links(html,url):
    out=[]
    for href,label in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',html,flags=re.I):
        lab=visible(label)
        absu=html_lib.unescape(urllib.parse.urljoin(url,href))
        if "download" in absu.lower() or "gtb_download.php" in absu or re.search(r"\.(pdf|hwp|hwpx|xls|xlsx|doc|docx)(?:\?|$)",absu,re.I):
            out.append({"label":lab[:180],"url":absu})
    return out[:20]
def main():
    out={}
    for key,url in SAMPLES.items():
        html=fetch_text(url)
        text=visible(html)
        out[key]={
            "url":url,
            "text_excerpt":text[:7000],
            "attachments":links(html,url),
        }
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
