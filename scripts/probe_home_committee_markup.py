"""One-shot probe for the homepage current-committee shortcut block."""
import re
from collect_current_members import fetch_text, BASE

def main():
    html=fetch_text(BASE+"/")
    m=re.search(r"상임위원회\s*바로가기",html)
    if not m:
        print("NO_SHORTCUT_HEADING")
        return
    pos=m.start()
    print("POS",pos,"LEN",len(html))
    print("SNIPPET_START")
    print(html[max(0,pos-3000):min(len(html),pos+16000)])
    print("SNIPPET_END")

if __name__=="__main__":
    main()
