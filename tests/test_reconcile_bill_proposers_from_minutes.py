import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reconcile_bill_proposers_from_minutes as r


class StrictOfficialMinutesEvidenceTests(unittest.TestCase):
    def test_full_roster_requires_adjacent_two_parentheses(self):
        parsed = r.parse_full_roster(
            "(박완희 의원 대표발의)(박완희, 남일현, 김영근 의원 발의)"
            "\n2. 다른 안건"
        )
        self.assertEqual(parsed["representative"], "박완희")
        self.assertEqual(parsed["all_names"], ["박완희", "남일현", "김영근"])

    def test_missing_full_roster_does_not_count(self):
        self.assertIsNone(r.parse_full_roster("(박완희 의원 대표발의)"))
        self.assertIsNone(r.parse_full_roster(
            "(박완희 의원 대표발의)(다른 의안에 대한 설명)"
        ))

    def test_representative_must_be_listed(self):
        self.assertIsNone(r.parse_full_roster(
            "(박완희 의원 대표발의)(남일현, 김영근 의원 발의)"
        ))

    def test_representative_only_never_builds_a_full_roster(self):
        rep = r.parse_representative_before(
            "의원 발의 의안으로 이재길 의원님이 대표 발의하신 "
        )
        self.assertEqual(rep["representative"], "이재길")
        self.assertIsNone(r.parse_full_roster("청주시장 및 관계공무원 출석요구의 건"))

    def test_ambiguous_list_rejected(self):
        self.assertIsNone(r.parse_full_roster(
            "(박완희 의원 대표발의)(박완희, 박완희 의원 발의)"
        ))


if __name__ == "__main__":
    unittest.main()
