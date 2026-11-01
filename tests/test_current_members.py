import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect_current_members as c


class CurrentMemberTests(unittest.TestCase):
    def test_parse_member_index_real_markup(self):
        html = """
        <div class="mobileLink">
          <li><a href="/memberHome/main.html?f_code=9999">가짜메뉴 의원</a></li>
        </div>
        <section class="member">
          <div class="box"><ul><li><a href="?idx=가">ㄱ</a></li></ul></div>
          <div class="memContent">
            <ul>
              <li>
                <dl>
                  <dt><img src="/UPDIR/memberphoto/4/4010_205.jpg" alt="곽현희 의원"></dt>
                  <dd class="name">곽현희</dd>
                  <dd>선거구 : 다선거구</dd>
                  <dd>소속정당 : 더불어민주당</dd>
                  <dd>소속위원회 : 의회운영위원회, 복지교육위원회</dd>
                  <dd class="btn">
                    <a href="/include/memberProfile.html?daesu=4&mcode=4010">상세프로필</a>
                    <a href="/memberHome/index.html?f_code=4010">누리집</a>
                  </dd>
                </dl>
              </li>
              <li>
                <dl>
                  <dt><img src="/UPDIR/memberphoto/4/4020_145.jpg" alt="김성수 의원"></dt>
                  <dd class="name">김성수</dd>
                  <dd>선거구 : 타선거구</dd>
                  <dd>소속정당 : 국민의힘</dd>
                  <dd>소속위원회 : 도시건설위원회</dd>
                  <dd class="btn">
                    <a href="/include/memberProfile.html?daesu=4&mcode=4020">상세프로필</a>
                    <a href="/memberHome/index.html?f_code=4020">누리집</a>
                  </dd>
                </dl>
              </li>
            </ul>
          </div>
        </section>
        """
        rows = c.parse_member_index(html)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["f_code"], "4010")
        self.assertEqual(rows[0]["m_code"], "4010")
        self.assertEqual(rows[0]["name"], "곽현희")
        self.assertEqual(rows[0]["district"], "다선거구")
        self.assertEqual(rows[0]["party"], "더불어민주당")
        self.assertEqual(
            rows[0]["committees"], ["의회운영위원회", "복지교육위원회"]
        )
        self.assertTrue(
            rows[0]["portrait_source_url"].endswith("/UPDIR/memberphoto/4/4010_205.jpg")
        )

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
