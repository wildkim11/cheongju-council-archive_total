import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_speeches_questions as c

class SpeechQuestionTests(unittest.TestCase):
    def test_five_minute_detail(self):
        html="""
        <div>홈 &gt; 의정활동 &gt; 5분자유발언</div>
        <div>5분자유발언</div>
        <h3>청주 삼겹런</h3>
        <div>홍순철 의원</div><div>2026-10-23</div>
        <a>회의록</a><a>영상보기</a>
        <p>무심천과 지역상권을 연결하는 정책을 제안합니다. 충분한 본문 내용입니다.</p>
        <div>목록</div>
        """
        row={"source_id":"607","official_url":"https://example/fiveRemark.html?number=607"}
        out=c.parse_detail(html,row,"5분자유발언")
        self.assertEqual(out["title"],"청주 삼겹런")
        self.assertEqual(out["speaker_name"],"홍순철")
        self.assertEqual(out["date"],"2026-10-23")
        self.assertIn("지역상권",out["body_text"])

    def test_city_question_requires_explicit_speaker_date(self):
        html="<div>시정질문</div><h3>제목</h3><p>본문만 있음</p>"
        with self.assertRaises(ValueError):
            c.parse_detail(html,{"source_id":"1","official_url":"x"},"시정질문")

if __name__=="__main__":
    unittest.main()
