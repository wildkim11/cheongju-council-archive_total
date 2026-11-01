import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from promote_verified_bill_rosters import promote_one


class PromoteOfficialMinutesEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "internal_number": "100",
            "term": 2,
            "proposer_type_list": "의원",
            "full_proposer_names": [],
            "representative_proposers": [],
            "co_proposers": [],
            "representative_proposer_text": "raw source field retained",
        }
        self.proof = {
            "status": "full_roster_evidenced_not_promoted",
            "verified_full_roster": {
                "representative": "박완희",
                "all_names": ["박완희", "남일현", "김영근"],
            },
            "evidence": [{
                "evidence_type": "complete_explicit_roster",
                "publication_status": "published",
                "every_name_unique_same_term": True,
                "representative": "박완희",
                "all_names": ["박완희", "남일현", "김영근"],
                "meeting_id": "cheongju_integrated:minutes-10",
                "meeting_url": "https://official.example/10",
                "source_excerpt": "의안(박완희 의원 대표발의)(박완희, 남일현, 김영근 의원 발의)",
            }],
        }
        self.meeting = {"cheongju_integrated:minutes-10": {
            "meeting_id": "cheongju_integrated:minutes-10",
            "term": 2, "official_url": "https://official.example/10",
            "date": "2021-05-25", "path": "archive/meetings/term-2/10.md",
            "content_sha256": "a"*64,
        }}

    def test_promote_exact_evidence_and_keep_raw_fields(self):
        result = promote_one(self.row, self.proof, self.meeting, "2026-11-02T01:00:00+09:00")
        self.assertEqual(result["representative_proposers"], ["박완희"])
        self.assertEqual(result["co_proposers"], ["남일현", "김영근"])
        self.assertEqual(result["representative_proposer_text"], "raw source field retained")
        self.assertEqual(result["proposer_roster_minutes_evidence"][0]["content_sha256"], "a"*64)
        self.assertEqual(self.row["full_proposer_names"], [])

    def test_no_candidate_or_representative_only_promotion(self):
        self.proof["status"] = "representative_only_not_full_roster"
        self.proof["verified_full_roster"] = None
        with self.assertRaises(ValueError):
            promote_one(self.row, self.proof, self.meeting, "2026-11-02T01:00:00+09:00")

    def test_unverified_name_rejected(self):
        self.proof["evidence"][0]["every_name_unique_same_term"] = False
        with self.assertRaises(ValueError):
            promote_one(self.row, self.proof, self.meeting, "2026-11-02T01:00:00+09:00")

    def test_institutional_bills_cannot_be_promoted(self):
        self.row["proposer_type_list"] = "시장"
        with self.assertRaises(ValueError):
            promote_one(self.row, self.proof, self.meeting, "2026-11-02T01:00:00+09:00")


if __name__ == "__main__":
    unittest.main()
