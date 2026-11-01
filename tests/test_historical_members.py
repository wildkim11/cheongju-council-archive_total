import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_historical_members as h


class HistoricalMembersTests(unittest.TestCase):
    def test_displayed_term_uses_page_heading(self):
        html="<nav>6대의원 5대의원</nav><h2>2대의원</h2>"
        self.assertEqual(h.displayed_term(html),2)

    def test_old_county_mapping_is_verified_not_inferred(self):
        self.assertTrue(h.OLD_COUNTY_PAGES[2].endswith("/oldgun/content/member5.html"))
        self.assertTrue(h.OLD_COUNTY_PAGES[6].endswith("/oldgun/content/member9.html"))

    def test_parse_old_city_real_markup(self):
        html="""
        <h1>5대의원</h1>
        <section class="member">
          <ul>
            <li><p><img src="/images/oldcity/member_05_01.jpg" alt="강신권" />
              <span><strong>강신권</strong>서운동,남1가</span></p></li>
            <li><p><img src="/images/oldcity/member_05_02.jpg" alt="강원모" />
              <span><strong>강원모</strong>강서2동</span></p></li>
          </ul>
        </section>
        """
        rows=h.parse_members(html,h.OLD_CITY_PAGES[5])
        self.assertEqual([r["name"] for r in rows],["강신권","강원모"])
        self.assertEqual(rows[0]["represented_area_label"],"서운동,남1가")
        self.assertEqual(rows[1]["represented_area_label"],"강서2동")
        self.assertTrue(rows[0]["portrait_source_url"].endswith("/images/oldcity/member_05_01.jpg"))

    def test_parse_old_county_real_markup(self):
        html="""
        <h1>2대의원</h1>
        <section class="member">
          <ul>
            <li><p><img src="/images/oldgun/member_02_01.jpg" alt="곽근완" />
              <span><strong>곽근완</strong></span></p></li>
            <li><p><img src="/images/oldgun/member_02_02.jpg" alt="김병국" />
              <span><strong>김병국</strong></span></p></li>
          </ul>
        </section>
        """
        rows=h.parse_members(html,h.OLD_COUNTY_PAGES[2])
        self.assertEqual([r["name"] for r in rows],["곽근완","김병국"])
        self.assertIsNone(rows[0]["represented_area_label"])

    def test_ignores_navigation_images_outside_member_section(self):
        html="""
        <nav><li><img src="/images/icon.png" alt="의원소개"></li></nav>
        <h1>5대의원</h1>
        <section class="member">
          <ul><li><img src="/images/oldcity/member.jpg" alt="홍길동"><strong>홍길동</strong>사창동</li></ul>
        </section>
        """
        rows=h.parse_members(html,h.OLD_CITY_PAGES[5])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["name"],"홍길동")

    def test_same_name_different_term_not_auto_merged(self):
        a=h.candidate_person_id("cheongju_old_city",5,"홍길동","https://x/a.jpg")
        b=h.candidate_person_id("cheongju_old_city",6,"홍길동","https://x/a.jpg")
        self.assertNotEqual(a,b)


if __name__=="__main__":
    unittest.main()
