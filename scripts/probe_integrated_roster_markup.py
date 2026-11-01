"""One-shot markup probe for integrated historical roster result."""
import re
from collect_integrated_historical_members import Session, fetch_term_html

def main():
    html=fetch_term_html(1,Session())
    markers=[]
    for pattern in [r"1\s*대\s*:",r"임기\s*:",r"선거구",r"memberHome",r"f_code"]:
        matches=list(re.finditer(pattern,html,flags=re.I))
        markers.append((pattern,len(matches),matches[0].start() if matches else None))
    print("MARKERS",markers)
    pos=None
    for pattern in [r"1\s*대\s*:",r"선거구",r"memberHome"]:
        m=re.search(pattern,html,flags=re.I)
        if m:
            pos=m.start();break
    if pos is None:
        print("NO_MEMBER_MARKER")
        print(html[:5000])
        return
    start=max(0,pos-1500);end=min(len(html),pos+5000)
    print("SNIPPET_START")
    print(html[start:end])
    print("SNIPPET_END")

if __name__=="__main__":
    main()
