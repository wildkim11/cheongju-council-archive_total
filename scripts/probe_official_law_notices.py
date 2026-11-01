"""Public official law-notice attachment discovery and bounded download probe.

A temporary output artifact only; no canonical source/bill changes.
"""
from __future__ import annotations
import datetime as dt, hashlib, html, http.client, json, re, ssl, time, urllib.parse
from pathlib import Path
from collect_bills import fetch_main, _visible

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports/bill-law-notice-attachment-probe.json"
OUT=ROOT/"reports/official-attachments-probe"
HOST="council.cheongju.go.kr"
NOTICE_2258="https://council.cheongju.go.kr/content/news/lawNoticeList.html?fidx=10627&opt=&page=45&pg=vv&sid=1000&sword="
PREVIEW_2258="https://council.cheongju.go.kr/synap/htmlViewer.xdo?fid=11367"
DOWNLOAD_2258="https://council.cheongju.go.kr/gtb_download.php?gtid=law&fid=11367"

def binary_fetch(url, max_bytes=12*1024*1024):
    split=urllib.parse.urlsplit(url)
    if split.scheme!="https" or split.hostname!=HOST:
        raise ValueError("Forbidden attachment origin")
    target=split.path+("?"+split.query if split.query else "")
    last=None
    for attempt in range(3):
        conn=http.client.HTTPSConnection(HOST,timeout=45,context=ssl.create_default_context())
        try:
            conn.request("GET",target,headers={"User-Agent":"CheongjuCouncilArchive/0.1","Accept":"*/*","Connection":"close"})
            r=conn.getresponse()
            data=r.read(max_bytes+1)
            if len(data)>max_bytes:
                raise ValueError("Attachment exceeded 12 MiB cap")
            return {"http_status":r.status,"content_type":r.getheader("Content-Type"),
                    "content_disposition":r.getheader("Content-Disposition"),
                    "body":data}
        except Exception as e:
            last=e
            time.sleep(min(4,2**attempt))
        finally:
            conn.close()
    raise last

def links_for_title(html_text):
    m=re.finditer("근로자종합복지관",html_text)
    out=[]
    for x in m:
        out.append({
            "context_visible":_visible(html_text[max(0,x.start()-260):x.end()+420])[:620],
            "raw_context":html_text[max(0,x.start()-220):x.end()+280][:600],
        })
        if len(out)>=9:
            break
    fidx=sorted(set(re.findall(r"fidx\s*=\s*[&quot;\"']?\s*([0-9]{3,6})",html_text,re.I)))
    return {"hits":out,"possible_fidx":fidx[:30]}

def run():
    report={"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode":"one-time public site preview and attachment probe",
            "original_bills_modified":False,"downloads":[],"html_pages":[]}
    for url in (PREVIEW_2258,NOTICE_2258):
        entry={"url":url,"fetch_status":"unknown"}
        try:
            raw=fetch_main(url)
            normalized=_visible(raw)
            entry.update({"fetch_status":"ok","length":len(raw),
                          "sha256":hashlib.sha256(raw.encode()).hexdigest(),
                          "content_matches":links_for_title(raw),
                          "visible_excerpt":normalized[:1200],
                          "page_refs":sorted(set(re.findall(r'(?:/synap/[^\s"\'<>]+|/gtb_download\.php\?[^\s"\'<>]+)',raw)))[:20]})
        except Exception as e:
            entry.update({"fetch_status":"error","reason":type(e).__name__+":"+str(e)[:230]})
        report["html_pages"].append(entry)
        print(json.dumps({"url":url,"status":entry["fetch_status"],
                          "length":entry.get("length"),"hits":len(entry.get("content_matches",{}).get("hits",[]))},ensure_ascii=False),flush=True)

    search_urls=[
        "https://council.cheongju.go.kr/content/news/lawNoticeList.html?"+
        urllib.parse.urlencode({"sid":"1000","sword":"근로자종합복지관","opt":"","page":page})
        for page in (1,2,3)
    ]
    for url in search_urls:
        entry={"url":url}
        try:
            raw=fetch_main(url)
            entry.update({"fetch_status":"ok",
                          "html_bytes":len(raw.encode()),
                          "hits":links_for_title(raw)})
        except Exception as e:
            entry.update({"fetch_status":"error","reason":type(e).__name__+":"+str(e)[:220]})
        report["html_pages"].append(entry)
        print(json.dumps({"url":url,"status":entry["fetch_status"],"matches":len(entry.get("hits",{}).get("hits",[]))},ensure_ascii=False),flush=True)
    OUT.mkdir(parents=True,exist_ok=True)
    for url,filename in [(DOWNLOAD_2258,"bill-2258-official-notice-original.bin")]:
        e={"url":url,"stored_name":filename,"status":"unknown"}
        try:
            response=binary_fetch(url)
            body=response.pop("body")
            e.update(response)
            e.update({"bytes":len(body),"sha256":hashlib.sha256(body).hexdigest()})
            if response["http_status"]==200 and len(body)>100 and not body[:20].lower().startswith(b"<!doctype"):
                (OUT/filename).write_bytes(body)
                e["status"]="downloaded_public_original"
            else:
                e["status"]="rejected_non_document"
        except Exception as ex:
            e.update({"status":"error","reason":type(ex).__name__+":"+str(ex)[:250]})
        report["downloads"].append(e)
        print(json.dumps({k:v for k,v in e.items() if k!="url"},ensure_ascii=False),flush=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    run()
