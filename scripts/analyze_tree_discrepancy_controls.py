"""Non-destructive case-control study for 13 term-only records.

All comparisons use archived official title, meeting date, committee code,
and inventory provenance; they do not change canonical source records.
"""
from __future__ import annotations
import collections
import datetime as dt
import json
from pathlib import Path
from audit_official_tree_discrepancy import classify, ROOT, IDS

def run(root=ROOT):
    index=json.loads((root/"indexes/integrated/meetings.json").read_text(encoding="utf-8"))
    rows=[classify(x) for x in index]
    cases=[x for x in rows if x["index_sources"]==["term"]]
    controls=[x for x in rows if x["index_sources"]==["term","year"]]
    post=[x for x in controls if x["post_session"]]
    if len(cases)!=13 or len(controls)!=2326 or len(post)!=108:
        raise ValueError(f"Unexpected inventory baseline: {len(cases)}, {len(controls)}, {len(post)}")
    if {x["source_id"] for x in cases}!=set(IDS):
        raise ValueError("Wrong exception IDs")
    def distribution(xs,func):
        return dict(sorted(collections.Counter(func(x) for x in xs).items(),key=lambda p:p[0]))
    def cross_year(x):
        return x["meeting_date"][:4] != x["session_end"][:4]
    report={
        "basis":"archived 2026-11-02 official term/year inventory labels, no current re-query",
        "sample_sizes":{"term_only_cases":len(cases),"year_and_term_controls":len(controls),
                        "year_and_term_post_session_controls":len(post)},
        "cross_calendar_year":{"term_only":sum(cross_year(x) for x in cases),
          "shared_post_session":sum(cross_year(x) for x in post),
          "term_only_session_end_dates":{x["source_id"]:x["session_end"] for x in cases},
          "shared_post_session_cross_year_examples":[{"source_id":x["source_id"],"date":x["meeting_date"],"session_end":x["session_end"]} for x in post if cross_year(x)][:25]},
        "post_session_days":{"term_only_min":min(x["days_after_session_end"] for x in cases),
          "term_only_max":max(x["days_after_session_end"] for x in cases),
          "controls_min":min(x["days_after_session_end"] for x in post),
          "controls_max":max(x["days_after_session_end"] for x in post)},
        "months":{"term_only":distribution(cases,lambda x:x["meeting_date"][5:7]),
                  "shared_post_session":distribution(post,lambda x:x["meeting_date"][5:7])},
        "years":{"term_only":distribution(cases,lambda x:x["meeting_date"][:4]),
                 "shared_post_session":distribution(post,lambda x:x["meeting_date"][:4])},
        "committees":{"term_only":distribution(cases,lambda x:x["committee_code"] or ""),
                      "shared_post_session":distribution(post,lambda x:x["committee_code"] or "")},
        "cases":[],"controls_same_year_and_committee":[],
    }
    for x in sorted(cases,key=lambda x:int(x["source_id"])):
        xd=dt.date.fromisoformat(x["meeting_date"])
        matched=[y for y in post
                 if y["committee_code"]==x["committee_code"]
                 and y["meeting_date"][:4]==x["meeting_date"][:4]]
        matched.sort(key=lambda y:(abs((dt.date.fromisoformat(y["meeting_date"])-xd).days),int(y["source_id"])))
        # Case-matched controls are diagnostic counterexamples, not a causal explanation.
        sample=[{"source_id":y["source_id"],"date":y["meeting_date"],
                 "days_after_session_end":y["days_after_session_end"],
                 "delta_calendar_days":abs((dt.date.fromisoformat(y["meeting_date"])-xd).days),
                 "official_url":y["official_url"]} for y in matched[:3]]
        report["cases"].append({
             "source_id":x["source_id"],"date":x["meeting_date"],"term":x["term"],
             "committee_code":x["committee_code"],"days_after_session_end":x["days_after_session_end"],
             "title":x["title"],"official_url":x["official_url"],
             "nearby_shared_post_session_controls_same_year_committee":sample,
        })
    report["controls_same_year_and_committee"]= [
       {"source_id":x["source_id"],
        "matched_control_count":len(x["nearby_shared_post_session_controls_same_year_committee"])}
        for x in report["cases"]
    ]
    report["interpretation"]="All 13 cases are post-session, but 108 shared records are also post-session. Date-after-session is neither sufficient nor an established root cause. Restrict hypothesis to evidence from official tree branch schema or source maintainer."
    path=root/"reports/integrated-tree-discrepancy-case-control.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
       "case_count":len(cases),"shared_post_session":len(post),
       "case_months":report["months"]["term_only"],
       "control_post_months":report["months"]["shared_post_session"],
       "case_committees":report["committees"]["term_only"],
       "control_post_committees":report["committees"]["shared_post_session"],
       "case_minmax_days":report["post_session_days"],
       "cross_calendar_year":report["cross_calendar_year"],
       "case_matched_same_year_and_committee":{
           x["source_id"]:len(x["nearby_shared_post_session_controls_same_year_committee"])
           for x in report["cases"]}},ensure_ascii=False,indent=2),flush=True)
    return report

if __name__=="__main__":
    run()
