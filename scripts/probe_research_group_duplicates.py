"""One-shot probe for duplicate research-group composition blocks."""
import re
from collect_current_members import fetch_text
from collect_current_research_groups import URL

TARGET="도서관을 사랑하는 의원 모임"

def main():
    html=fetch_text(URL)
    print("LEN",len(html))
    print("YEAR_MARKERS",[(m.start(),m.group(0)) for m in re.finditer(r"2026\s*년도?\s*구성현황",html)])
    occ=list(re.finditer(TARGET,html))
    print("TARGET_OCCURRENCES",len(occ),[m.start() for m in occ])
    for i,m in enumerate(occ,1):
        pos=m.start()
        print(f"OCC_{i}_START")
        print(html[max(0,pos-3500):min(len(html),pos+6500)])
        print(f"OCC_{i}_END")

if __name__=="__main__":
    main()
