import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_historical_committees as c

class HistoricalCommitteeCollectorTests(unittest.TestCase):
    def test_parse_text_roster_with_count(self):
        html="""
        <div>
        경제문화위원회(8) 홍성각 정무신 김진석, 배성철, 변은영, 안광수, 이상조, 홍순철
        복지교육위원회(7) 한동순 홍혜진 곽현희, 김은숙, 노순옥, 마재광, 박노학
        </div>
        """
        rows=c.parse_rosters(html)
        by={r["committee_name"]:r for r in rows}
        self.assertEqual(len(by["경제문화위원회"]["participants"]),8)
        self.assertEqual(by["경제문화위원회"]["participants"][0],{"name":"홍성각","role":"위원장"})
        self.assertEqual(by["경제문화위원회"]["participants"][1],{"name":"정무신","role":"부위원장"})

    def test_parse_special_committee(self):
        html="""
        <div>
        예산결산특별위원회(13) 정영석 박승찬 정재우, 김태순, 정연숙, 이상조, 이완복, 한동순, 홍성각, 김은숙, 박근영, 신민수, 김완식
        윤리특별위원회(7) 박근영 정재우 최재호, 김완식, 이인숙, 박승찬, 홍순철
        </div>
        """
        rows=c.parse_rosters(html)
        self.assertEqual({r["committee_name"] for r in rows},{"예산결산특별위원회","윤리특별위원회"})
        self.assertEqual(c._committee_type("윤리특별위원회"),"special_committee")

    def test_incomplete_count_is_not_promoted_by_text_parser(self):
        html="<div>예산결산특별위원회(13) 정영석 박승찬 정재우, 김태순</div>"
        self.assertEqual(c._parse_text_rows(html),[])

    def test_source_specific_period_wins(self):
        src={
            "effective_start_date":"2024-08-26",
            "effective_end_date":None,
            "period_precision":"per_committee_explicit_period",
            "committee_periods":{
                "예산결산특별위원회":{
                    "start_date":"2024-08-26","end_date":"2025-06-30","period_precision":"exact_date"
                }
            }
        }
        self.assertEqual(
            c._source_period(src,"예산결산특별위원회"),
            ("2024-08-26","2025-06-30","exact_date")
        )

if __name__=="__main__":
    unittest.main()
