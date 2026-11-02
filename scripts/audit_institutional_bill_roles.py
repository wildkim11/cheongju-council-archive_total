"""Reconcile institutional-type bill person-link provenance without promoting roles.

Read-only QA ledger of five source-type/relationship conflicts. Offline mode
validates all raw rows against the current source-only analyzer export and flags
the exact official fields responsible for the name extraction. --live makes at
most five bounded official-page GET requests (12s each, no retries) with verified
TLS and records raw HTML hashes and labelled source values.

A person printed under representative/co-proposer-labelled fields of a bill
with institutional proposer_type is NOT automatically a legislative proposer.
No raw data, indexes, or analyzer exports are edited by this audit.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import html as html_lib
import http.client
import json
import re
import ssl
import urllib.parse
from pathlib import Path

from collect_bills import _table_fields, _visible

ROOT=Path(__file__).resolve().parents[1]
EXPECTED={"375":("위원장",1),"2177":("의장",6),"2180":("시장",12),
          "3265":("위원장",12),"3266":("위원장",13)}
ALLOWED_HOSTS={"council.cheongju.go.kr","councilrec.cheongju.go.kr"}
SUSPECT_CHARS=re.compile(r"[\ufffd\u25a1\u00c0-\u00ff]")
OUT="reports/institutional-bill-44-person-links-provenance.json"

def load(root,path):
    return json.loads((root/path).read_text(encoding="utf-8"))

def sha(root,path):
    return hashlib.sha256((root/path).read_bytes()).hexdigest()

def member_type(b):
    # Deliberate veto on institutional type from *either* official field.
    a=str(b.get("proposer_type_list") or "").strip()
    d=str(b.get("proposer_type") or "").strip()
    return {"list":a,"detail":d,"agree":a==d,
            "both_prove_member":a=="의원" and d=="의원",
            "institutional_veto":a!="의원" or d!="의원"}

def report_offline(root=ROOT):
    bills=load(root,"archive/bills/items.json")
    links=load(root,"archive/bills/proposer_memberships.json")
    manifest=load(root,"exports/analyzer/manifest.json")
    by_id={str(x["internal_number"]):x for x in bills}
    if len(by_id)!=len(bills) or len(bills)!=3394:
        raise ValueError("Unexpected bill source baseline")
    expected=set(EXPECTED)
    if any(x not in by_id for x in expected):
        raise ValueError("Missing institutional exception bill")
    # All original relationship rows still have a corresponding canonical bill.
    if any(str(x.get("internal_number")) not in by_id for x in links):
        raise ValueError("Orphan original person link")
    institutional=collections.defaultdict(list)
    for line in links:
        bill=by_id[str(line["internal_number"])]
        if member_type(bill)["institutional_veto"]:
            institutional[str(line["internal_number"])].append(line)
    actual={k:len(v) for k,v in institutional.items()}
    if actual!={k:v[1] for k,v in EXPECTED.items()}:
        raise ValueError(f"Disagreed institutional group or sizes: {actual}")
    # The source relationship must be preserved byte-for-byte in quarantine.
    for dataset,source_path in [
        ("bill_proposers","archive/bills/proposer_memberships.json"),
        ("bill_proposers_member_only",None),
        ("bill_proposers_institutional_type_quarantine",None)
    ]:
        info=manifest["datasets"][dataset]
        path=root/info["path"]
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=info["sha256"]:
            raise ValueError(f"Manifest digest mismatch: {dataset}")
    q_path=root/manifest["datasets"]["bill_proposers_institutional_type_quarantine"]["path"]
    raw_quarantine=[json.loads(s) for s in q_path.read_text(encoding="utf-8").splitlines() if s.strip()]
    if len(raw_quarantine)!=44 or raw_quarantine != [x for x in links if str(x["internal_number"]) in expected]:
        raise ValueError("Quarantine does not reproduce each 44 original link in original order")
    member_file=root/manifest["datasets"]["bill_proposers_member_only"]["path"]
    member_rows=[json.loads(s) for s in member_file.read_text(encoding="utf-8").splitlines() if s.strip()]
    if len(member_rows)!=11377 or len(links)!=11421 or any(str(x["internal_number"]) in expected for x in member_rows):
        raise ValueError("Member proposer view leaked institutional relationships")
    cases=[]
    for k,(actor,n) in EXPECTED.items():
        b=by_id[k]
        t=member_type(b)
        if t["both_prove_member"] or not t["institutional_veto"]:
            raise ValueError(f"Type unexpectedly personal: {k}")
        if actor not in (t["list"],t["detail"]):
            raise ValueError(f"Expected institution actor absent in source types: {k}")
        allnames=b.get("full_proposer_names") or []
        rep=b.get("representative_proposers") or []
        co=b.get("co_proposers") or []
        raw_fields={a:b.get(a) for a in (
            "representative_proposer_text","co_proposers_text","proposer_type_list",
            "proposer_type","bill_type","proposal_date","processed_date_list",
            "proposer_roster_parse_status","proposer_roster_repair_method")
            if a in b}
        raw_names=[str(x.get("person_name")) for x in institutional[k]]
        cases.append({
          "internal_number":k,"term":b["term"],"bill_number":b.get("bill_number"),
          "session":b.get("session"),"title":b["title"],
          "official_url":b["official_url"],"actor_label_in_bill":actor,
          "proposer_type_fields":t,
          "raw_bill_fields":raw_fields,
          "source_person_link_count":n,
          "source_raw_person_names":raw_names,
          "source_raw_link_roles":[{"person_name":x.get("person_name"),"raw_proposer_role":x.get("proposer_role"),
                                    "resolution_status":x.get("resolution_status"),
                                    "source_url":x.get("source_url")} for x in institutional[k]],
          "parsed_representative_names":rep,"parsed_co_names":co,"parsed_all_names":allnames,
          "distinct_person_names":len(set(raw_names)),
          "duplicate_person_names":{name:count for name,count in collections.Counter(raw_names).items() if count>1},
          "possible_replacement_or_mojibake":bool(SUSPECT_CHARS.search(str(raw_fields)+str(raw_names))),
          "role_assertion":"UNVERIFIED_NOT_PERSONAL_PROPOSER_STATISTIC",
          "reconciliation_note":"Institution actor type and parsed person field are different dimensions. Raw 'representative' or 'co_proposer' fields must not be promoted to personal legislative proposer without documentary proof.",
        })
    return {
      "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "audit_scope":"read-only source-type reconciliation, not a reclassification of people",
      "source_bill_rows":len(bills),
      "source_person_relationships":len(links),
      "member_only_rows":len(member_rows),
      "institutional_quarantine_rows":len(raw_quarantine),
      "canonical_bills_sha256":sha(root,"archive/bills/items.json"),
      "canonical_links_sha256":sha(root,"archive/bills/proposer_memberships.json"),
      "case_count":len(cases),
      "cases":cases,
      "live_page_probe":None,
      "safe_for_personal_statistics_dataset":"bill_proposers_member_only",
      "source_files_modified":False,
    }

def bounded_html(url):
    parts=urllib.parse.urlsplit(url)
    if parts.scheme!="https" or parts.hostname not in ALLOWED_HOSTS:
        raise ValueError("Official source host not allowed")
    ctx=ssl.create_default_context()
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.set_ciphers("DEFAULT")
    conn=http.client.HTTPSConnection(parts.hostname,timeout=12,context=ctx)
    try:
        path=parts.path+("?" +parts.query if parts.query else "")
        conn.request("GET",path,headers={"User-Agent":"CheongjuCouncilArchive-RoleQA/0.1","Accept":"text/html"})
        resp=conn.getresponse()
        payload=resp.read(3_500_000)
        if resp.status!=200:
            raise ValueError(f"Source HTTP {resp.status}")
        return payload.decode("utf-8-sig","replace")
    finally:
        conn.close()

def verify_live(report):
    results=[]
    for case in report["cases"]:
        r={"internal_number":case["internal_number"],"official_url":case["official_url"]}
        try:
            raw=bounded_html(case["official_url"])
            fields=_table_fields(raw)
            visible=_visible(raw)
            label_fields={k:fields.get(k) for k in
                ("의안번호","발의자","대표발의자","공동발의","제안의원","회기","의안종류")
                if k in fields}
            r.update({
              "status":"ok","html_sha256":hashlib.sha256(raw.encode("utf-8")).hexdigest(),
              "html_utf8_bytes":len(raw.encode("utf-8")),
              "official_labelled_fields":label_fields,
              "official_html_visible_title":case["title"] in visible,
              "stored_list_actor_label":case["actor_label_in_bill"],
              "official_bill_proposer_actor_text":fields.get("발의자"),
              "source_type_same_actor":str(fields.get("발의자") or "").strip()==case["actor_label_in_bill"],
              "official_person_label_existence":{k:k in fields for k in ("대표발의자","공동발의","제안의원")},
              "documentary_role_inference":"NOT_SUPPORTED_BY_OFFICIAL_DETAIL_FIELDS_ALONE",
            })
        except Exception as e:
            r.update({"status":"error","error_class":type(e).__name__,"error":str(e)[:230]})
        results.append(r)
        print(json.dumps({"id":r["internal_number"],"status":r["status"],
                          "matches_actor":r.get("source_type_same_actor")},ensure_ascii=False),flush=True)
    report["live_page_probe"]={
       "checked_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
       "source":"direct official detail HTML, 5 requests maximum, HTTPS verified, single-attempt",
       "success_count":sum(r["status"]=="ok" for r in results),
       "error_count":sum(r["status"]=="error" for r in results),
       "details":results,
    }
    return report

def run(root=ROOT,live=False):
    report=report_offline(root)
    if live:
        verify_live(report)
    p=root/OUT
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"bill_ids":[c["internal_number"] for c in report["cases"]],
          "raw_rows":report["source_person_relationships"],
          "member_only":report["member_only_rows"],
          "quarantine":report["institutional_quarantine_rows"],
          "live_ok":(report["live_page_probe"] or {}).get("success_count"),
          "live_errors":(report["live_page_probe"] or {}).get("error_count"),
          "source_files_modified":report["source_files_modified"]},ensure_ascii=False,indent=2),flush=True)
    return report

if __name__=="__main__":
    arg=argparse.ArgumentParser()
    arg.add_argument("--live",action="store_true")
    args=arg.parse_args()
    run(live=args.live)
