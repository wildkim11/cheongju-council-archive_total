"""One-shot markup probe for current committee roster structures."""
import re
from collect_current_members import fetch_text, BASE

URLS={
    "standing":f"{BASE}/content/committee/coIntroduce_C306.html",
    "budget_special":f"{BASE}/content/committee/coIntroduce_G100.html",
    "ethics_special":f"{BASE}/content/committee/coIntroduce_G140.html",
    "hearing":f"{BASE}/content/committee/coIntroduce_G250.html",
}

def inspect(label,url):
    html=fetch_text(url)
    print("==",label,url,"LEN",len(html))
    for pattern in [r"위원장",r"부위원장",r"class=[\"'][^\"']*member",r"class=[\"'][^\"']*committee",r"<li",r"<dl"]:
        ms=list(re.finditer(pattern,html,flags=re.I))
        print("MARK",pattern,len(ms),[m.start() for m in ms[:5]])
    for needle in [r"위원장",r"부위원장"]:
        m=re.search(needle,html)
        if m:
            pos=m.start()
            print("SNIPPET_START",label)
            print(html[max(0,pos-2500):min(len(html),pos+10000)])
            print("SNIPPET_END",label)
            break

def main():
    for label,url in URLS.items():
        inspect(label,url)

if __name__=="__main__":
    main()
