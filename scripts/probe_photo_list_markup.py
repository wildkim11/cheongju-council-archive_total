"""One-time inspection of photo activity list markup around detail links."""
import json,re
from collect_current_members import fetch_text
URL="https://council.cheongju.go.kr/content/activity/photo.html?gtid=photo&page=1"
def main():
    html=fetch_text(URL)
    out=[]
    for m in re.finditer(r'fidx=(\d+)',html):
        start=max(0,m.start()-900);end=min(len(html),m.end()+1300)
        snippet=html[start:end]
        out.append({"fidx":m.group(1),"snippet":snippet})
        if len(out)>=3: break
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
