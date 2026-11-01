import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_board_activities as c

class BoardActivityTests(unittest.TestCase):
    def test_press_detail(self):
        html="""
        <div>홈 &gt; 의회소식 &gt; 보도자료</div>
        <div>보도자료</div>
        <h3>전문가 초청특강 개최</h3>
        <div>청주시의회</div><div>2026-10-15</div><div>조회수 120</div>
        <a href="/gtb_download.php?gtid=notice&fid=10">사진.jpg</a>
        <p>정책 기반 마련을 위한 전문가 특강을 개최했다. 참석자들은 의견을 나눴다.</p>
        <div>목록</div>
        """
        row={"source_id":"22047","official_url":"https://example/bodo.html?fidx=22047"}
        out=c.parse_detail(html,row,c.CONFIG["press"])
        self.assertEqual(out["title"],"전문가 초청특강 개최")
        self.assertEqual(out["author_label"],"청주시의회")
        self.assertEqual(out["date"],"2026-10-15")
        self.assertTrue(out["attachments"])
        self.assertIn("정책 기반",out["body_text"])

    def test_debate_allows_metadata_only(self):
        html="""
        <div>토론회</div><h3>지원 조례 제정 토론회</h3>
        <div>복지교육위원회</div><div>2024-06-10</div><div>조회수 10</div>
        <div>목록</div>
        """
        row={"source_id":"1","official_url":"https://example/debate.html?fidx=1"}
        out=c.parse_detail(html,row,c.CONFIG["debate"])
        self.assertEqual(out["author_label"],"복지교육위원회")
        self.assertIsNone(out["body_text"])

    def test_photo_keeps_links_not_binary(self):
        html="""
        <div>포토의정</div><h3>현장 방문</h3><div>2026-10-31</div>
        <a href="/photo_download.html?fid=23089">원본 사진받기</a><div>목록</div>
        """
        row={"source_id":"6644","official_url":"https://example/photo.html?fidx=6644"}
        out=c.parse_detail(html,row,c.CONFIG["photo"])
        self.assertEqual(out["date"],"2026-10-31")
        self.assertEqual(len(out["attachments"]),1)
        self.assertIn("photo_download",out["attachments"][0]["official_url"])

if __name__=="__main__":
    unittest.main()
