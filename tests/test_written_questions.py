import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_written_questions as c

class WrittenQuestionTests(unittest.TestCase):
    def test_list_row_uses_detail_record_number(self):
        html="""
        <table><tr>
          <td>16</td><td>2026-03-12</td><td>이영신</td>
          <td>청주시 공무원 포상 제도의 관리·운영 체계 점검을 위한 서면질문</td>
          <td><a href="/content/activity/questionLetter.html?pg=vv&number=29&page=1&sword=">질문파일</a></td>
          <td><a href="/paper_down.html?number=29&gb=ans">답변파일</a></td>
        </tr></table>
        """
        rows=c.parse_page(html,c.URL+"?page=1")
        self.assertEqual(rows[0]["list_number"],"16")
        self.assertEqual(rows[0]["source_id"],"29")
        self.assertEqual(rows[0]["speaker_name"],"이영신")
        self.assertIn("number=29",rows[0]["detail_url"])
        self.assertIn("gb=ans",rows[0]["answer_file_url_list"])

    def test_detail_real_question_answer_links(self):
        html="""
        <a href="/paper_down.html?number=29&gb=qna">질문 파일</a>
        <a href="/paper_down.html?number=29&gb=ans">답변 파일</a>
        """
        files=c.parse_detail_files(html,"https://council.cheongju.go.kr/content/activity/questionLetter.html?number=29")
        self.assertIn("gb=qna",files["question_file_url"])
        self.assertIn("gb=ans",files["answer_file_url"])

if __name__=="__main__":
    unittest.main()
