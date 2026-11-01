import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import discover_historical_committee_sources as d


class HistoricalCommitteeDiscoveryTests(unittest.TestCase):
    def test_parse_candidate_links(self):
        html="""
        <table>
          <tr><td><a href="/content/committee/coActivity_C101.html?fidx=14287&page=1&pg=vv">
            제3대 청주시의회 전반기 상임위원회 구성 및 상임위원장단 선출
          </a></td></tr>
          <tr><td><a href="?fidx=999">일반 간담회</a></td></tr>
          <tr><td><a href="/content/committee/coActivity_G100.html?fidx=20087">
            제3대 청주시의회 마지막 예산결산특별위원장 정재우 의원 선출
          </a></td></tr>
        </table>
        """
        rows=d.parse_board_candidates(html,"standing",d.BOARD_SEEDS["standing"])
        self.assertEqual([r["fidx"] for r in rows],[14287,20087])

    def test_irrelevant_link_is_ignored(self):
        html='<a href="?fidx=1">현장방문 실시</a>'
        self.assertEqual(
            d.parse_board_candidates(html,"standing",d.BOARD_SEEDS["standing"]),[]
        )


if __name__=="__main__":
    unittest.main()
