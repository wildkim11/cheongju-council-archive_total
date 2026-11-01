import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_bills as b

class BillCollectorTests(unittest.TestCase):
    def test_parse_list_row(self):
        html="""
        <table><tr>
          <td>133</td><td>106 회</td>
          <td><a href="https://councilrec.cheongju.go.kr/content/minutes/iframe_bill_view1.html?daesu=4&number=3492">지방의회법 제정 촉구 결의안</a></td>
          <td>의원</td><td></td><td>원안가결</td><td>2026-10-23</td>
        </tr></table>
        """
        rows=b.parse_list_page(html,4,b.LIST_URL)
        self.assertEqual(rows[0]["internal_number"],"3492")
        self.assertEqual(rows[0]["bill_number_list"],"133")
        self.assertEqual(rows[0]["result_list"],"원안가결")

    def test_parse_detail_full_roster(self):
        html="""
        <div>
        의안번호 133 의안종류 결의안 발의자 의원
        발의일 2026-10-08 회기 106 회 소관위원회
        대표발의자 최동식
        공동발의 곽현희, 김성수, 변은영, 이상조, 허 선
        본회의 상정일 2026-10-23 처리일 2026-10-23 처리결과 원안가결
        </div>
        """
        row={
            "internal_number":"3492","term":4,"council_scope":b.COUNCIL_SCOPE,
            "title":"지방의회법 제정 촉구 결의안","official_url":"https://councilrec.cheongju.go.kr/x?number=3492",
            "bill_number_list":"133","session_list":"106 회","proposer_type_list":"의원",
            "committee_list":None,"result_list":"원안가결","processed_date_list":"2026-10-23",
            "list_source_url":b.LIST_URL
        }
        parsed=b.parse_detail(html,row)
        self.assertEqual(parsed["bill_type"],"결의안")
        self.assertEqual(parsed["representative_proposers"],["최동식"])
        self.assertIn("허선",parsed["co_proposers"])
        self.assertEqual(parsed["full_proposer_names"][0],"최동식")

    def test_non_member_proposer_does_not_create_names(self):
        self.assertEqual(b._names("시장"),[])
        self.assertEqual(b._names("의장"),[])

if __name__=="__main__":
    unittest.main()
