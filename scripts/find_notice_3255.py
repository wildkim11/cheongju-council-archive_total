"""Read-only discovery of a 2025 withdrawn bill's official public notice.

Search a bounded set of *official* indexed listing pages; record only direct
matched title+date and original attachment metadata. No bill modifications.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, re, urllib.parse
from pathlib import Path
from collect_bills import fetch_main,_visible
from probe_bill_official_attachments import links
from probe_official_law_notices import binary_fetch

ROOT=Path(__file__).resolve().parents[1]
SITE="https://council.cheongju.go.kr"
PREFIX="/content/news/lawNoticeList.html"
NEEDLE="근로자종합복지관 운영 조례 일부개정조례안"
OUT=ROOT/"reports/official-attachments-probe"
REPORT=ROOT/"reports/bill-3255-official-public-notice-discovery.json"

def inspect(html,number):
    found=[]
    for m in re.finditer("근로자종합복지관",html):
        snippet=html[max(0,m.start()-700):min(len(html),m.end()+700)]
        if "2025" not in snippet and "2025" not in _visible(snippet):
            continue
        fidx=re.findall(r"fidx\s*=\s*([0-9]+)",snippet)
        found.append({
            "page":number,"context":_visible(snippet)[:800],
            "raw_context":snippet[:1050],"fidx_near_title":sorted(set(fidx)),
        })
    return found[:10]

def run():
    report={
        "generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_scope":"public council lawNoticeList.html listing, 2025-11-13 law notice",
        "bill_internal_number":"3255","bill_number":"1042",
        "target_2025_distinct_from_2024_mayor_bill":True,
        "searched_pages":[],
        "matching_rows":[],
        "matched_detail":None,
        "downloads":[],
        "canonical_archive_edited":False
    }
    for page in range(1,25):
        url=f"{SITE}{PREFIX}?sid=1000&page={page}"
        item={"page":page,"status":"unknown"}
        try:
            raw=fetch_main(url)
            matches=inspect(raw,page)
            item.update({"status":"ok","bytes":len(raw.encode()),"matches":len(matches)})
            report["matching_rows"].extend(matches)
        except Exception as ex:
            item.update({"status":"error","error":type(ex).__name__+":"+str(ex)[:140]})
        report["searched_pages"].append(item)
        if page%4==0 or report["matching_rows"]:
            print(json.dumps(item,ensure_ascii=False),flush=True)
        if report["matching_rows"]:
            break

    # Resolve only a directly matched official notice URL, not a same-title bill.
    for match in report["matching_rows"]:
        ids=match["fidx_near_title"]
        if not ids:
            continue
        for fidx in ids:
            detail_url=f"{SITE}{PREFIX}?fidx={fidx}&pg=vv&sid=1000"
            raw=fetch_main(detail_url)
            text=_visible(raw)
            if NEEDLE not in text or "2025" not in text:
                continue
            candidate_links=links(raw,detail_url)
            good=[x for x in candidate_links if x.get("safe_absolute_url")
                  and "/gtb_download.php" in x["safe_absolute_url"]]
            report["matched_detail"]={
                "official_url":detail_url,"html_sha256":hashlib.sha256(raw.encode()).hexdigest(),
                "visible_excerpt":text[-3500:],
                "candidate_attachment_links":good,
            }
            OUT.mkdir(parents=True,exist_ok=True)
            for i,x in enumerate(good[:4]):
                link=x["safe_absolute_url"]
                response=binary_fetch(link)
                body=response.pop("body")
                e={"original_url":link,"status":response.get("http_status"),
                   "response":response,"sha256":hashlib.sha256(body).hexdigest(),
                   "bytes":len(body)}
                if response.get("http_status")==200 and len(body)>100 and not body[:10].startswith(b"<!"):
                    fname=f"bill-3255-official-notice-{i+1}.bin"
                    (OUT/fname).write_bytes(body)
                    e["artifact_path"]=str((OUT/fname).relative_to(ROOT))
                report["downloads"].append(e)
            break
        if report["matched_detail"]:
            break
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"pages_scanned":len(report["searched_pages"]),
                      "matching_rows":len(report["matching_rows"]),
                      "detail":report["matched_detail"]["official_url"] if report["matched_detail"] else None,
                      "downloads":[{"status":e["status"],"bytes":e["bytes"],"path":e.get("artifact_path")} for e in report["downloads"]]},ensure_ascii=False))
    return report

if __name__=="__main__":
    run()
