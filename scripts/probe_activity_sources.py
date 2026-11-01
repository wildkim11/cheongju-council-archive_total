"""One-time probe for official activity source URLs and list markup."""
import json,re,urllib.parse
from collect_current_members import fetch_text, BASE

SEEDS=[
    f"{BASE}/content/activity/question.html",
    f"{BASE}/content/activity/fiveRemark.html",
    f"{BASE}/content/news/bodo.html",
    f"{BASE}/content/activity/debate.html",
    f"{BASE}/content/activity/photo.html",
]
TARGETS=("서면질문","건의/결의문","5분자유발언","시정질문","보도자료","토론회","포토의정")

def vis(raw):
    raw=re.sub(r"<[^>]+>"," ",raw)
    return re.sub(r"\s+"," ",raw).strip()

def main():
    out=[]
    for seed in SEEDS:
        html=fetch_text(seed)
        target_links=[]
        for href,label in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',html,flags=re.I):
            text=vis(label)
            if any(t in text for t in TARGETS):
                target_links.append({"text":text,"url":urllib.parse.urljoin(seed,href)})
        detail_links=[]
        for href,label in re.findall(r'<a\b[^>]*href=["\']([^"\']*(?:fidx=|pg=vv|number=)[^"\']*)["\'][^>]*>([\s\S]*?)</a>',html,flags=re.I):
            text=vis(label)
            if text:
                detail_links.append({"text":text[:180],"url":urllib.parse.urljoin(seed,href)})
        rows=[]
        for tr in re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>",html,flags=re.I)[:8]:
            cells=[vis(x) for x in re.findall(r"<t[dh]\b[^>]*>([\s\S]*?)</t[dh]>",tr,flags=re.I)]
            if cells: rows.append(cells)
        out.append({
            "seed":seed,
            "target_links":target_links[:30],
            "detail_links":detail_links[:12],
            "sample_rows":rows[:6],
        })
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
