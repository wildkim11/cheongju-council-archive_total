import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import find_bill_minutes_fallback as f


class BillMinutesFallbackTests(unittest.TestCase):
    def test_spacing_and_typographic_title_variants(self):
        body = "안건 청주시 지역상품 우선 구매에 관한 조례안(김의원 발의)입니다."
        matches = f.candidate_occurrences(body, "청주시 지역상품 우선구매에 관한 조례안")
        self.assertTrue(matches)
        self.assertEqual(matches[0]["match"], "exact_title")

    def test_partial_title_marked_weak_evidence(self):
        body = "2022년 청주시 사회적 고립청년 지원에 관한 조례 제정 안건입니다."
        hits = f.candidate_occurrences(body, "청주시 사회적 고립청년 지원에 관한 조례안")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["match"], "partial_prefix_only")

    def test_session_matching(self):
        self.assertTrue(f.session_match("29회", "제029회 청주시의회 제1차 본회의"))
        self.assertFalse(f.session_match("29회", "제30회 청주시의회 제1차 본회의"))
        self.assertFalse(f.session_match(
            "70회",
            "제2대 의회(2018. 07. 01 ~ 2022. 06. 30 : 제37회 ~ 제70회) 제68회[임시회] 본회의 제1호"
        ))
        self.assertTrue(f.session_match(
            "68회",
            "제2대 의회(2018. 07. 01 ~ 2022. 06. 30 : 제37회 ~ 제70회) 제68회[임시회] 본회의 제1호"
        ))

    def test_date_window(self):
        self.assertTrue(f.near_day("2021-05-28", "2021-04-09", "2021-05-28"))
        self.assertFalse(f.near_day("2018-01-01", "2021-04-09", "2021-05-28"))

    def test_absent_title_yields_no_candidates(self):
        self.assertEqual(f.candidate_occurrences("다른 안건", "청주시 노동존중 기본 조례안"), [])


if __name__ == "__main__":
    unittest.main()
