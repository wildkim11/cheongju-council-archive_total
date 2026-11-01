import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_current_members as c


class CurrentMemberTests(unittest.TestCase):
    def test_parse_member_index(self):
        html = """
        <ul>
          <li>
            <img src="/upload/member/a.jpg" alt="홍길동 의원">
            <a href="/memberHome/content/bill.html?f_code=10001">상세프로필</a>
          </li>
        </ul>
        """
        rows = c.parse_member_index(html)
        self.assertEqual(rows[0]["f_code"], "10001")
        self.assertEqual(rows[0]["name"], "홍길동")
        self.assertTrue(rows[0]["portrait_source_url"].endswith("/upload/member/a.jpg"))

    def test_parse_profile(self):
        html = """
        <div>선거구 : 나 선거구</div>
        <div>소속정당 : 테스트정당</div>
        <div>소속위원회 : 경제문화위원회, 의회운영위원회</div>
        <div>전화번호 : 1234</div>
        <div>이메일 : test@example.com</div>
        <h4>경력사항</h4>
        <ul><li>현) 제4대 테스트 의회 위원</li><li>전) 테스트 위원장</li></ul>
        <div>의정활동</div>
        """
        row = c.parse_profile(html)
        self.assertEqual(row["district"], "나 선거구")
        self.assertEqual(row["party"], "테스트정당")
        self.assertEqual(row["committees"], ["경제문화위원회", "의회운영위원회"])
        self.assertIn("현) 제4대 테스트 의회 위원", row["career"])

    def test_stable_person_id(self):
        self.assertEqual(c.stable_person_id("10230"), "person-fcode-10230")


if __name__ == "__main__":
    unittest.main()
