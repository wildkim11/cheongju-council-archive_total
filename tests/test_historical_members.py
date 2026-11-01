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

    def test_parse_member_block(self):
        html="""
        <h2>5대의원</h2>
        <ul>
          <li><img src="/oldcity/images/member/a.jpg" alt="강신권강신권서운동,남1가"></li>
          <li><img src="/oldcity/images/member/b.jpg" alt="강원모강원모강서2동"></li>
        </ul>
        """
        rows=h.parse_members(html,h.OLD_CITY_PAGES[5])
        self.assertEqual([r["name"] for r in rows],["강신권","강원모"])
        self.assertTrue(rows[0]["portrait_source_url"].startswith("https://council.cheongju.go.kr/"))

    def test_same_name_different_term_not_auto_merged(self):
        a=h.candidate_person_id("cheongju_old_city",5,"홍길동","https://x/a.jpg")
        b=h.candidate_person_id("cheongju_old_city",6,"홍길동","https://x/a.jpg")
        self.assertNotEqual(a,b)

if __name__=="__main__":
    unittest.main()
