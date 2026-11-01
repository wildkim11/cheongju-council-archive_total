import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_written_questions as c

class WrittenQuestionTests(unittest.TestCase):
    def test_list_row_with_question_answer_files(self):
        html="""
        <table><tr>
          <td>16</td><td>2026-03-12</td><td>이영신</td>
          <td>청주시 공무원 포상 제도의 관리·운영 체계 점검을 위한 서면질문</td>
          <td><a href="/gtb_download.php?gtid=q&fid=1">질문파일</a></td>
          <td><a href="/gtb_download.php?gtid=q&fid=2">답변파일</a></td>
        </tr></table>
        """
        rows=c.parse_page(html,c.URL+"?page=1")
        self.assertEqual(rows[0]["source_id"],"16")
        self.assertEqual(rows[0]["speaker_name"],"이영신")
        self.assertIn("fid=1",rows[0]["question_file_url"])
        self.assertIn("fid=2",rows[0]["answer_file_url"])

if __name__=="__main__":
    unittest.main()
