import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from probe_bill_official_attachments import attr_map, links, ALLOWED

class AttachmentDiscoveryTests(unittest.TestCase):
    def test_url_and_attribute_parser(self):
        html='<a href="/file/download?id=1" onclick="getFile(1)">의안181.hwp</a>'
        got=links(html,"https://council.cheongju.go.kr/notice")
        self.assertEqual(got[0]["safe_absolute_url"],"https://council.cheongju.go.kr/file/download?id=1")
        self.assertEqual(got[0]["attributes"]["onclick"],"getFile(1)")
    def test_external_link_not_marked_safe(self):
        html='<a href="https://other.example/file.hwp">첨부파일</a>'
        got=links(html,"https://council.cheongju.go.kr/notice")
        self.assertIsNone(got[0]["safe_absolute_url"])
if __name__=="__main__":
    unittest.main()
