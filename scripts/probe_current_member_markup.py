"""One-shot markup probe for the current member list main content."""
import re
from collect_current_members import fetch_text, LIST_URL

def main():
    html=fetch_text(LIST_URL)
    print("URL",LIST_URL,"LEN",len(html))

    patterns=[
        r'class=["\'][^"\']*\bmember[^"\']*["\']',
        r'class=["\'][^"\']*memberList[^"\']*["\']',
        r'class=["\'][^"\']*memberSearchList[^"\']*["\']',
        r'<h1[^>]*>[^<]*의원',
    ]
    for pattern in patterns:
        ms=list(re.finditer(pattern,html,flags=re.I))
        print("MARK",pattern,len(ms),[m.start() for m in ms[:8]])

    # Show neighborhood of each member-class marker in the main body.
    markers=list(re.finditer(r'class=["\'][^"\']*\bmember[^"\']*["\']',html,flags=re.I))
    for idx,m in enumerate(markers[:5],1):
        pos=m.start()
        print(f"SNIPPET_{idx}_START")
        print(html[max(0,pos-2500):min(len(html),pos+14000)])
        print(f"SNIPPET_{idx}_END")

if __name__=="__main__":
    main()
