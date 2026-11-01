import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_integrated_historical_members as h

class IntegratedHistoricalMemberTests(unittest.TestCase):
    def test_hidden_field(self):
        html='<input type="hidden" name="CSRFToken" value="abc123">'
        self.assertEqual(h._hidden(html,"CSRFToken"),"abc123")

    def test_parse_roster_and_exact_term(self):
        html="""
        <ul>
          <li>
            <a href="/memberHome/content/profile.html?f_code=2060">
              <img src="/upload/member/a.jpg" alt="임은성 의원">
              임은성 (2대:라 선거구 )
            </a>
          </li>
          <li>
            <a href="/include/memberProfile.html?daesu=3&mcode=TEST3">
              <img src="/UPDIR/memberphoto/3/test.jpg" alt="한병수">
              한병수 (3대: )
            </a>
            임기:2022. 7.1 ~ 2023. 2.2.
          </li>
        </ul>
        """
        rows=h.parse_term_members(html,2)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["name"],"임은성")
        self.assertEqual(rows[0]["district"],"라 선거구")
        self.assertEqual(rows[0]["official_profile_code"],"2060")

        rows3=h.parse_term_members(html,3)
        self.assertEqual(rows3[0]["start_date"],"2022-07-01")
        self.assertEqual(rows3[0]["end_date"],"2023-02-02")

    def test_official_code_connects_terms(self):
        a={
            "term":1,"name":"홍길동","district":"가 선거구","portrait_source_url":None,
            "official_profile_code":"123","official_profile_code_type":"f_code"
        }
        b={
            "term":2,"name":"홍길동","district":"나 선거구","portrait_source_url":None,
            "official_profile_code":"123","official_profile_code_type":"f_code"
        }
        self.assertEqual(h.person_id(a),h.person_id(b))

    def test_mcode_is_term_scoped_not_cross_term_identity(self):
        a={
            "term":1,"name":"김병국","district":"다 선거구",
            "portrait_source_url":None,
            "official_profile_code":"B103",
            "official_profile_code_type":"mcode",
        }
        b={
            "term":2,"name":"김병국","district":"가 선거구",
            "portrait_source_url":None,
            "official_profile_code":"B103",
            "official_profile_code_type":"mcode",
        }
        self.assertNotEqual(h.person_id(a),h.person_id(b))

    def test_real_markup_shape_with_mcode(self):
        html="""
        <ul>
          <li>
            <a href="/include/memberProfile.html?daesu=1&mcode=8030">
              <span class="pic"><img src="/UPDIR/memberphoto/1/a.jpg" alt="김기동"></span>
              <span class="name">김기동<br><b>(1대:라 선거구 )</b></span>
            </a>
          </li>
        </ul>
        """
        rows=h.parse_term_members(html,1)
        self.assertEqual(rows[0]["name"],"김기동")
        self.assertEqual(rows[0]["official_profile_code_type"],"mcode")
        self.assertEqual(rows[0]["official_profile_code"],"8030")
        self.assertEqual(rows[0]["district"],"라 선거구")

    def test_no_code_does_not_merge_same_name_across_terms(self):
        a={"term":1,"name":"홍길동","district":"가 선거구","portrait_source_url":None,"official_profile_code":None}
        b={"term":2,"name":"홍길동","district":"가 선거구","portrait_source_url":None,"official_profile_code":None}
        self.assertNotEqual(h.person_id(a),h.person_id(b))

if __name__=="__main__":
    unittest.main()
