import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_historical_research_metadata as r

class HistoricalResearchMetadataTests(unittest.TestCase):
    def test_attachment_link_parsing(self):
        html='<a href="/gtb_download.php?gtid=news&fid=14138">공고문.pdf</a>'
        rows=r.attachment_links(html,"https://council.cheongju.go.kr/content/news/notice.html")
        self.assertEqual(rows[0]["official_attachment_id"],"14138")
        self.assertEqual(rows[0]["official_attachment_group"],"news")
        self.assertEqual(rows[0]["file_type"],"pdf")

    def test_group_name_from_report_attachment(self):
        self.assertEqual(
            r._group_name_from_attachment("연구활동결과보고(문화예술연구회).pdf"),
            "문화예술연구회"
        )
        self.assertEqual(
            r._group_name_from_attachment("2025년 의원 연구단체 연구활동 보고서(청주공항 비상을 바라는 모임).pdf"),
            "청주공항 비상을 바라는 모임"
        )

    def test_registered_groups(self):
        text="등록단체 : 3개 단체(가 연구회, 나 모임, 다 포럼)"
        self.assertEqual(r._registered_groups(text),["가 연구회","나 모임","다 포럼"])

if __name__=="__main__":
    unittest.main()
