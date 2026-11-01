"""One-shot diagnostics for the integrated historical-member search form."""
import json
import re
from collect_historical_members import fetch, INTEGRATED_HISTORY_URL

def main():
    html=fetch(INTEGRATED_HISTORY_URL)
    forms=re.findall(r"<form\b[^>]*>",html,flags=re.I)
    selects=[]
    for m in re.finditer(r"<select\b([^>]*)>([\s\S]*?)</select>",html,flags=re.I):
        attrs=m.group(1)
        body=m.group(2)
        name=re.search(r'name=["\']?([^"\'\s>]+)',attrs,flags=re.I)
        options=[]
        for opt in re.finditer(r"<option\b([^>]*)>([\s\S]*?)</option>",body,flags=re.I):
            oattrs=opt.group(1)
            text=re.sub(r"<[^>]+>"," ",opt.group(2))
            value=re.search(r'value=["\']?([^"\'\s>]+)',oattrs,flags=re.I)
            options.append({
                "value": value.group(1) if value else None,
                "text": re.sub(r"\s+"," ",text).strip(),
            })
        selects.append({"name":name.group(1) if name else None,"options":options})
    inputs=[]
    for tag in re.findall(r"<input\b[^>]*>",html,flags=re.I):
        def attr(key):
            m=re.search(rf'{key}=["\']?([^"\'\s>]+)',tag,flags=re.I)
            return m.group(1) if m else None
        inputs.append({"name":attr("name"),"type":attr("type"),"value":attr("value")})
    links=sorted(set(
        re.findall(r'href=["\']([^"\']*integrationCheongju[^"\']*)',html,flags=re.I)
    ))
    print(json.dumps({
        "url":INTEGRATED_HISTORY_URL,
        "forms":forms[:10],
        "selects":selects,
        "inputs":inputs[:30],
        "links":links[:50],
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
