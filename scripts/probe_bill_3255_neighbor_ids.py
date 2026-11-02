"""Locate withdrawn 2025 council bill notice by adjacent source-record IDs.

The notice site can omit withdrawn posts from the visible listing. This probe
tries a small bounded interval of official IDs around the surviving 2025-11-13
notice (fidx=20491, announcement 2025-106). No canonical archive writes.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from collect_bills import fetch_main, _visible
from probe_official_law_notices import binary_fetch
from probe_bill_official_attachments import links

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/"reports/bill-3255-neighboring-official-notice-probe.json"
NEEDLE="청주시 근로자종합복지관 운영 조례 일부개정조례안"
BASE="https://council.cheongju.go.kr/content/news/lawNoticeList.html?fidx={id}&pg=vv&sid=1000"

def evidence(raw,fidx):
    text=_visible(raw)
    marker=text.find("입법예고")
    location=text.find("근로자종합복지관")
    if location>=0:
        snippet=text[max(0,location-170):location+650]
    else:
        snippet=text[max(0,marker):max(0,marker)+360] if marker>=0 else text[:400]
    return {
        "fidx":fidx,
        "html_sha256":hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "title_present":NEEDLE in text,
        "2025_date_present":"2025-11-13" in text or "2025. 11. 13." in text,
        "body_excerpt":snippet,
        "attachment_links":[x for x in links(raw, BASE.format(id=fidx)) if
                 "/gtb_download.php" in (x.get("safe_absolute_url") or "")][:8],
    }

def run(root=ROOT):
    # 20491 is a known official announcement from 2025-11-13. Stay local.
    ids=list(range(20477,20495))
    inspected=[]
    downloads=[]
    for fidx in ids:
        url=BASE.format(id=fidx)
        row={"url":url,"fidx":fidx}
        try:
            raw=fetch_main(url)
            row.update({"status":"ok",**evidence(raw,fidx)})
        except Exception as ex:
            row.update({"status":"error","error":type(ex).__name__+":"+str(ex)[:170]})
        inspected.append(row)
        print(json.dumps({key:row.get(key) for key in ("fidx","status","title_present","2025_date_present")},
                         ensure_ascii=False),flush=True)
        if row.get("title_present") and row.get("2025_date_present"):
            for i,link in enumerate(row.get("attachment_links",[])[:3]):
                download=link["safe_absolute_url"]
                res=binary_fetch(download)
                content=res.pop("body")
                record={"url":download,"http_status":res["http_status"],
                        "content_length":len(content),
                        "sha256":hashlib.sha256(content).hexdigest(),
                        "content_disposition":res["content_disposition"]}
                if res["http_status"]==200 and len(content)>100 and content[:8]==bytes.fromhex("d0cf11e0a1b11ae1"):
                    relative=f"reports/official-attachments-probe/bill-3255-neighbor-{fidx}-{i}.hwp"
                    target=root/relative
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(content)
                    record["stored_path"]=relative
                downloads.append(record)
    result={
        "generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "status":"completed_official_neighbor_probe",
        "candidate_fidx_count":len(ids),
        "candidates_with_exact_title":[x["fidx"] for x in inspected if x.get("title_present")],
        "candidates_with_2025_title":[x["fidx"] for x in inspected if x.get("title_present") and x.get("2025_date_present")],
        "inspected":inspected,"downloads":downloads,
        "no_canonical_files_modified":True,
        "warning":"Failed lookup does not prove that withdrawn notice never existed.",
    }
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"candidate_2025_fidx":result["candidates_with_2025_title"],
                      "downloaded_originals":[x.get("stored_path") for x in downloads if x.get("stored_path")]},
                     ensure_ascii=False))
    return result

if __name__=="__main__":
    run()
