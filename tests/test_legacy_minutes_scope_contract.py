"""No-network tests for separate legacy old-city and old-county source staging."""
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import legacy_minutes_scope_contract as l

def official_verified_leaf(scope,source_id):
    proof=json.loads((l.__file__ and Path(l.__file__).resolve().parents[1]/
                     "reports/official-preintegration-two-leaves-readonly-20261102.json")
                     .read_text(encoding="utf-8"))
    branch=next(x for x in proof["council_results"] if x["scope"]==scope)
    leaf=next(x for x in branch["leaf_source_samples"] if x["var12"]==source_id)
    return branch,leaf

class LegacyScopeSafetyTests(unittest.TestCase):
    def test_two_actual_source_leaf_ids_stage_separately_without_fabricated_status(self):
        c,cl=official_verified_leaf("cheongju_old_city","4355")
        g,gl=official_verified_leaf("cheongwon_old_county","2581")
        a=l.normalize_verified_legacy_leaf("cheongju_old_city",c["selected_term"],
            c["selected_session"],c["selected_committee_code"],cl)
        b=l.normalize_verified_legacy_leaf("cheongwon_old_county",g["selected_term"],
            g["selected_session"],g["selected_committee_code"],gl)
        qa=l.check_stage_scope_collisions([a,b])
        self.assertEqual(qa["distinct_scope_aware_meeting_ids"],2)
        self.assertEqual(a["meeting_id"],"cheongju_old_city:minutes-4355")
        self.assertEqual(b["meeting_id"],"cheongwon_old_county:minutes-2581")
        self.assertEqual(a["year"],2014)
        self.assertEqual(b["year"],2014)
        self.assertEqual(a["source_tree_publication_code"],"N")
        self.assertEqual(b["source_tree_publication_code"],"N")
        self.assertIsNone(a["normalized_publication_status"])
        self.assertIsNone(b["normalized_publication_status"])
        self.assertFalse(a["eligible_for_public_analyzer"])
        self.assertFalse(qa["operational_archive_write_allowed"])

    def test_same_numeric_id_in_both_councils_is_not_identity_collision(self):
        city,cl=official_verified_leaf("cheongju_old_city","4355")
        county,gl=official_verified_leaf("cheongwon_old_county","2581")
        cp=copy.deepcopy(cl)
        gp=copy.deepcopy(gl)
        cp["var12"]="500"
        gp["var12"]="500"
        a=l.normalize_verified_legacy_leaf("cheongju_old_city",9,
            city["selected_session"],"A010",cp)
        b=l.normalize_verified_legacy_leaf("cheongwon_old_county",6,
            county["selected_session"],"A010",gp)
        self.assertNotEqual(a["meeting_id"],b["meeting_id"])
        self.assertEqual(l.check_stage_scope_collisions([a,b])["verified_staging_rows"],2)

    def test_term_namespace_mix_is_blocked(self):
        city,leaf=official_verified_leaf("cheongju_old_city","4355")
        with self.assertRaisesRegex(ValueError,"DOES_NOT_BELONG"):
            l.normalize_verified_legacy_leaf("cheongwon_old_county",9,
                city["selected_session"],"A010",leaf)

    def test_post_merger_future_date_never_promoted_as_legacy(self):
        city,leaf=official_verified_leaf("cheongju_old_city","4355")
        leaf=dict(leaf,text="제2차(2026.10.14 수요일)")
        with self.assertRaisesRegex(ValueError,"OUTSIDE_PREINTEGRATION"):
            l.normalize_verified_legacy_leaf("cheongju_old_city",9,
                city["selected_session"],"A010",leaf)

    def test_wrong_official_body_url_or_analysis_promotion_refused(self):
        city,leaf=official_verified_leaf("cheongju_old_city","4355")
        row=l.normalize_verified_legacy_leaf("cheongju_old_city",9,
            city["selected_session"],"A010",leaf)
        row["official_url"]=row["official_url"].replace("/minuteschj/","/minuteschw/")
        with self.assertRaisesRegex(ValueError,"OFFICIAL_URL"):
            l.check_stage_scope_collisions([row])
        row["official_url"]=row["official_url"].replace("/minuteschw/","/minuteschj/")
        row["eligible_for_public_analyzer"]=True
        with self.assertRaisesRegex(ValueError,"ANALYZER_PROMOTION"):
            l.check_stage_scope_collisions([row])

if __name__=="__main__":
    unittest.main()
