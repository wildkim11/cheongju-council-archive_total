"""One-shot markup probe for the current member list."""
import re
from collect_current_members import fetch_text, LIST_URL

def main():
    html=fetch_text(LIST_URL)
    print("URL",LIST_URL,"LEN",len(html))
    for pattern in [r"f_code",r"memberHome",r"class=[\"']member",r"<li",r"<article",r"의원"]:
        ms=list(re.finditer(pattern,html,flags=re.I))
        print("MARK",pattern,len(ms),ms[0].start() if ms else None)

    # Prefer the first official member-home link and show its containing neighborhood.
    m=re.search(r'href=["\']([^"\']*memberHome[^"\']*f_code=[^"\']+)["\']',html,flags=re.I)
    if not m:
        m=re.search(r"f_code=",html,flags=re.I)
    if not m:
        print("NO_FCODE_MARKER")
        print(html[:6000])
        return
    pos=m.start()
    print("SNIPPET_START")
    print(html[max(0,pos-2500):min(len(html),pos+9000)])
    print("SNIPPET_END")

if __name__=="__main__":
    main()
