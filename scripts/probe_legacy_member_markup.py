"""One-shot markup probe for legacy council member pages."""
import re
from collect_historical_members import fetch, OLD_CITY_PAGES, OLD_COUNTY_PAGES

def inspect(label,url):
    html=fetch(url)
    print("==",label,url,"LEN",len(html))
    for pattern in [r"member",r"UPDIR",r"<li",r"<dd",r"<div",r"강신권",r"곽근완"]:
        ms=list(re.finditer(pattern,html,flags=re.I))
        print("MARK",pattern,len(ms),ms[0].start() if ms else None)
    pos=None
    for pattern in [r"강신권",r"곽근완",r"UPDIR",r"memberphoto",r"<img"]:
        m=re.search(pattern,html,flags=re.I)
        if m:
            pos=m.start();break
    if pos is None:
        print(html[:5000]);return
    print("SNIPPET_START")
    print(html[max(0,pos-1800):min(len(html),pos+7000)])
    print("SNIPPET_END")

def main():
    inspect("oldcity-term5",OLD_CITY_PAGES[5])
    inspect("oldcounty-term2",OLD_COUNTY_PAGES[2])

if __name__=="__main__":
    main()
