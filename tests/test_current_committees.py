import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_current_committees as c

class CurrentCommitteeTests(unittest.TestCase):
    def test_discover_committees(self):
        html="""
        <a href="/content/committee/coIntroduce_OLD.html">과거특별위원회</a>
        <section class="mCmt">
          <ul>
            <li><a href="/content/committee/coIntroduce_C306.html">경제문화<span>위원회</span></a></li>
            <li><a href="/content/committee/coIntroduce_G100.html">예산결산<span>특별위원회</span></a></li>
          </ul>
        </section>
        """
        rows=c.discover_committees(html)
        self.assertEqual({r["committee_code"] for r in rows},{"C306","G100"})

    def test_parse_roles_and_stale_period(self):
        html="""
        <h1>예산결산특별위원회 위원회 소개</h1>
        <div>위원회 임기 : 2025. 7. 1. ~ 2026. 6. 30.</div>
        <h3>위원장, 부위원장</h3>
        <ul class="chairman">
          <li><span class="name">남일현 위원장</span><br>(행정안전위원회)</li>
          <li><span class="name">이상조 부위원장</span><br>(경제문화위원회)</li>
        </ul>
        <h3>위원</h3>
        <ul class="member">
          <li><span class="name">김재년 위원</span><br>(농업정책위원회)</li>
          <li><span class="name">허선 위원</span><br>(보건환경위원회)</li>
        </ul>
        """
        row=c.parse_committee_page(html,"예산결산특별위원회")
        self.assertEqual(len(row["roles"]),4)
        self.assertTrue(row["period_conflict_with_current_term"])

    def test_current_period_not_conflict(self):
        html="""
        <div>위원회 임기 : 2026. 7. 1. ~ 2027. 6. 30.</div>
        <ul class="chairman">
          <li><span class="name">홍성각 위원장</span></li>
          <li><span class="name">정무신 부위원장</span></li>
        </ul>
        <ul class="member">
          <li><span class="name">이상조 위원</span></li>
        </ul>
        """
        row=c.parse_committee_page(html,"경제문화위원회")
        self.assertFalse(row["period_conflict_with_current_term"])

    def test_committee_type(self):
        self.assertEqual(c.committee_type("경제문화위원회"),"standing_committee")
        self.assertEqual(c.committee_type("윤리특별위원회"),"special_committee")
        self.assertEqual(c.committee_type("인사청문위원회"),"other_committee")

if __name__=="__main__":
    unittest.main()
