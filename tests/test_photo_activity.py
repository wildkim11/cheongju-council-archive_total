import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import collect_photo_activity as c

class PhotoActivityTests(unittest.TestCase):
    def test_parse_list_only_metadata(self):
        html="""
        <ul class="photolist">
          <li>
            <a href="?fidx=6644&gtid=photo&pg=vv&page=1"><p class="pic"><img alt="무심천 직지유등문화제"></p></a>
            <p class="subject"><a href="?gtid=photo&pg=vv&sid=1000&page=1&fidx=6644&opt=&sword=">무심천 직지유등문화제</a></p>
            <p class="date">2026-10-31</p>
          </li>
        </ul>
        """
        rows=c.parse_page(html,c.URL+"&page=1")
        self.assertEqual(rows[0]["source_id"],"6644")
        self.assertEqual(rows[0]["title"],"무심천 직지유등문화제")
        self.assertEqual(rows[0]["date"],"2026-10-31")
        self.assertFalse(rows[0]["binary_mirrored"])
        self.assertIn("fidx=6644",rows[0]["official_url"])

if __name__=="__main__":
    unittest.main()
