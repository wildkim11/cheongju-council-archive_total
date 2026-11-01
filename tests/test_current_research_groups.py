import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_current_research_groups as r


class CurrentResearchGroupTests(unittest.TestCase):
    def test_parse_current_group_table(self):
        html="""
        <h3>2026년도 구성현황</h3>
        <table>
          <tr><th>연번</th><th>연구단체명</th><th>인원</th><th>참여의원</th></tr>
          <tr>
            <td>1</td>
            <td>청주시 강호축 미래전략 연구회</td>
            <td>3명</td>
            <td>신민수(대표), 임은성, 허 선</td>
          </tr>
        </table>
        """
        groups=r.parse_groups(html,2026)
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]["member_count"],3)
        self.assertEqual(groups[0]["participants"][0],{"name":"신민수","role":"대표"})
        self.assertEqual(groups[0]["participants"][2]["name"],"허선")

    def test_rejects_member_count_mismatch(self):
        html="""
        <h3>2026년도 구성현황</h3>
        <table>
          <tr><th>연번</th><th>연구단체명</th><th>인원</th><th>참여의원</th></tr>
          <tr><td>1</td><td>시험 연구회</td><td>3명</td><td>신민수(대표), 허선</td></tr>
        </table>
        """
        with self.assertRaises(ValueError):
            r.parse_groups(html,2026)

    def test_requires_exactly_one_representative(self):
        with self.assertRaises(ValueError):
            r._parse_participants("신민수, 임은성")

    def test_normalize_spaced_name(self):
        self.assertEqual(r._normalize_name("허 선"),"허선")


if __name__=="__main__":
    unittest.main()
