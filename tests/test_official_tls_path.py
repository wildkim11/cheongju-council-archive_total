import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import diagnose_official_tls_path_readonly as d


class TLSOnlyNoHTTPTests(unittest.TestCase):
    def test_host_allowlist_rejects_unrelated_before_network(self):
        with self.assertRaises(ValueError):
            d.tls_check("example.com")

    def test_diagnostic_never_claims_http_or_release(self):
        def fake(host):
            return {"host":host,"tls":"not_verified","attempts":1,"http_requests":0}
        with tempfile.TemporaryDirectory() as folder:
            report=d.diagnose(check=fake,out=Path(folder)/"test-report.json")
            self.assertEqual(report["tls_handshakes_attempted"],2)
            self.assertEqual(report["http_requests"],0)
            self.assertEqual(report["status"],"OFFICIAL_TLS_UNAVAILABLE_FROM_THIS_RUNNER")
            self.assertFalse(report["live_collection_authorized"])

    def test_main_domain_success_is_not_viewer_success(self):
        def fake(host):
            return {"host":host,"tls":"verified" if host=="council.cheongju.go.kr" else "not_verified"}
        with tempfile.TemporaryDirectory() as folder:
            report=d.diagnose(check=fake,out=Path(folder)/"test-report.json")
            self.assertEqual(report["status"],"MINUTES_HOST_TLS_UNAVAILABLE_BUT_COUNCIL_MAIN_HOST_AVAILABLE")
            self.assertFalse(report["live_collection_authorized"])


if __name__=="__main__":
    unittest.main()
