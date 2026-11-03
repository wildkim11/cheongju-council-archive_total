"""Institutional bill source provenance must not be treated as personal sponsors."""
import json
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import audit_institutional_bill_roles as a

class InstitutionalRoleTests(unittest.TestCase):
    def test_no_personal_type_when_one_source_label_is_institutional(self):
        for source in (
            {"proposer_type_list":"의원","proposer_type":"시장"},
            {"proposer_type_list":"위원장","proposer_type":"의원"},
            {"proposer_type_list":"의장","proposer_type":"의장"},
            {"proposer_type_list":"의원","proposer_type":None},
        ):
            self.assertTrue(a.member_type(source)["institutional_veto"])
        self.assertFalse(a.member_type({"proposer_type_list":"의원","proposer_type":"의원"})["institutional_veto"])

    def test_current_snapshot_quarantine_is_lossless(self):
        result=a.report_offline()
        self.assertEqual(result["source_bill_rows"],len(json.loads((a.ROOT/"archive/bills/items.json").read_text())))
        self.assertGreaterEqual(result["case_count"],5)
        self.assertEqual(result["source_person_relationships"],result["member_only_rows"]+result["institutional_quarantine_rows"])
        self.assertEqual(result["member_only_rows"],json.loads((a.ROOT/"exports/analyzer/manifest.json").read_text())["datasets"]["bill_proposers_member_only"]["rows"])
        self.assertGreaterEqual(result["institutional_quarantine_rows"],44)
        self.assertEqual({r["internal_number"]:r["source_person_link_count"] for r in result["cases"] if r["internal_number"] in {"375","2177","2180","3265","3266"}},
                         {"375":1,"2177":6,"2180":12,"3265":12,"3266":13})
        self.assertTrue(all(x["role_assertion"]=="UNVERIFIED_NOT_PERSONAL_PROPOSER_STATISTIC" for x in result["cases"]))

    def test_live_probe_does_not_promote_proposer_role(self):
        sample={"cases":[{"internal_number":"2180",
                          "official_url":"https://councilrec.cheongju.go.kr/content/minutes/iframe_bill_view1.html?number=2180",
                          "actor_label_in_bill":"시장","title":"테스트"}]}
        html="""<table><tr><th>발의자</th><td>시장</td></tr><tr><th>대표발의자</th><td>홍길동</td></tr></table>"""
        with patch.object(a,"bounded_html",return_value=html):
            a.verify_live(sample)
        p=sample["live_page_probe"]["details"][0]
        self.assertEqual(p["status"],"ok")
        self.assertTrue(p["source_type_same_actor"])
        self.assertEqual(p["official_labelled_fields"]["대표발의자"],"홍길동")
        self.assertEqual(p["documentary_role_inference"],"NOT_SUPPORTED_BY_OFFICIAL_DETAIL_FIELDS_ALONE")

    def test_live_errors_are_not_taken_as_missing_documents(self):
        sample={"cases":[{"internal_number":"375","official_url":"https://council.cheongju.go.kr/test",
                          "actor_label_in_bill":"위원장","title":"테스트"}]}
        with patch.object(a,"bounded_html",side_effect=TimeoutError("fixture timeout")):
            a.verify_live(sample)
        self.assertEqual(sample["live_page_probe"]["error_count"],1)
        self.assertEqual(sample["live_page_probe"]["details"][0]["status"],"error")

if __name__=="__main__":
    unittest.main()
