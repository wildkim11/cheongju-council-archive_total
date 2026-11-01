"""One-time live smoke probe for official bill detail parsing."""
import json
from collect_bills import fetch_any, parse_detail, COUNCIL_SCOPE

URL="https://councilrec.cheongju.go.kr/content/minutes/iframe_bill_view1.html?daesu=4&number=3492"

def main():
    row={
        "internal_number":"3492",
        "council_scope":COUNCIL_SCOPE,
        "term":4,
        "bill_number_list":"133",
        "session_list":"106 회",
        "title":"지방자치의 완성과 지방의회 독립성 강화를 위한 「지방의회법」 제정 촉구 결의안",
        "proposer_type_list":"의원",
        "committee_list":None,
        "result_list":"원안가결",
        "processed_date_list":"2026-10-23",
        "official_url":URL,
        "list_source_url":"https://council.cheongju.go.kr/content/activity/billForProcessing.html?daesu=4",
    }
    parsed=parse_detail(fetch_any(URL),row)
    result={
        "internal_number":parsed["internal_number"],
        "bill_number":parsed.get("bill_number"),
        "bill_type":parsed.get("bill_type"),
        "proposal_date":parsed.get("proposal_date"),
        "representative_proposers":parsed.get("representative_proposers"),
        "co_proposer_count":len(parsed.get("co_proposers") or []),
        "full_proposer_count":len(parsed.get("full_proposer_names") or []),
    }
    print(json.dumps(result,ensure_ascii=False))
    if result["bill_type"]!="결의안":
        raise SystemExit("Unexpected bill type")
    if "최동식" not in (result["representative_proposers"] or []):
        raise SystemExit("Representative proposer parse failed")
    if result["full_proposer_count"] < 40:
        raise SystemExit("Full proposer roster unexpectedly small")

if __name__=="__main__":
    main()
