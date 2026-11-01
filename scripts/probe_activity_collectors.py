"""One-time live smoke check of activity collectors without writing archive data."""
import json
from collect_current_members import fetch_text
from activity_common import discover_links
import collect_speeches_questions as sq
import collect_written_questions as wq
import collect_board_activities as ba

def main():
    out={}
    for kind,url in {
        "five_minute":"https://council.cheongju.go.kr/content/activity/fiveRemark.html?pg=vv&number=607&page=1&sword=&ssid=",
        "city_question":"https://council.cheongju.go.kr/content/activity/question.html?pg=vv&number=87&page=1&sword=&ssid=",
    }.items():
        cfg=sq.CONFIG[kind]
        row={"source_id":"607" if kind=="five_minute" else "87","official_url":url}
        r=sq.parse_detail(fetch_text(url),row,cfg["section_label"])
        out[kind]={
            "title":r["title"],"speaker":r["speaker_name"],"date":r["date"],
            "body_chars":len(r["body_text"]),"attachments":len(r["attachments"])
        }

    wh=fetch_text(wq.URL+"?page=1")
    wr=wq.parse_page(wh,wq.URL+"?page=1")
    out["written_question"]={
        "rows_page1":len(wr),
        "sample":{k:wr[0].get(k) for k in ("source_id","date","speaker_name","title","question_file_url","answer_file_url")} if wr else None
    }

    for kind in ("suggestion_resolution","press","debate","photo"):
        cfg=ba.CONFIG[kind]
        listed=discover_links(cfg["list_url"],cfg["detail_pattern"],max_pages=1)
        row=listed[0]
        r=ba.parse_detail(fetch_text(row["official_url"]),row,cfg)
        out[kind]={
            "source_id":r["source_id"],"title":r["title"],"author":r["author_label"],
            "date":r["date"],"body_chars":len(r["body_text"] or ""),
            "attachments":len(r["attachments"])
        }
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
