import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import discover_historical_research_sources as d

class HistoricalResearchDiscoveryTests(unittest.TestCase):
    def test_notice_candidate(self):
        html='<a href="/content/news/notice.html?fidx=123&pg=vv">2024년 의원 연구단체 구성 현황 공고</a>'
        rows=d.parse_candidates(html,d.NOTICE)
        self.assertEqual(rows[0]["year"],2024)
        self.assertEqual(rows[0]["source_family"],"notice")

    def test_report_candidate(self):
        html='<a href="/content/activity/researchReport.html?fidx=999&pg=vv">2025년 청주시의회 의원 연구단체 연구활동보고서</a>'
        rows=d.parse_candidates(html,d.REPORT)
        self.assertEqual(rows[0]["year"],2025)
        self.assertEqual(rows[0]["source_family"],"research_report")

    def test_irrelevant_ignored(self):
        html='<a href="?fidx=1">일반 공지</a>'
        self.assertEqual(d.parse_candidates(html,d.NOTICE),[])

if __name__=="__main__":
    unittest.main()
