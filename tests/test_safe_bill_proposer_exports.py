import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from export_analyzer import partition_bill_proposer_rows
class SourceOnlyBillProposerExportTests(unittest.TestCase):
    def test_partitions_without_discarding_original_rows(self):
        bills=[
            {"internal_number":"a","proposer_type_list":"의원"},
            {"internal_number":"b","proposer_type_list":"시장"},
            {"internal_number":"c","proposer_type_list":"의장"},
        ]
        links=[
            {"internal_number":"a","person_name":"가나다","proposer_role":"representative"},
            {"internal_number":"b","person_name":"라마바","proposer_role":"representative"},
            {"internal_number":"c","person_name":"사아자","proposer_role":"co_proposer"},
        ]
        before=json.dumps(links,ensure_ascii=False)
        personal,quarantine=partition_bill_proposer_rows(bills,links)
        self.assertEqual(len(personal),1)
        self.assertEqual(len(quarantine),2)
        self.assertEqual(before,json.dumps(links,ensure_ascii=False))
        self.assertEqual(personal[0],links[0])
        self.assertEqual(quarantine,links[1:])
    def test_conflicting_official_proposer_labels_fail_closed(self):
        bills=[
            {"internal_number":"institution_list","proposer_type_list":"위원장","proposer_type":"의원"},
            {"internal_number":"institution_detail","proposer_type_list":"의원","proposer_type":"시장"},
            {"internal_number":"matching_person","proposer_type_list":"의원","proposer_type":"의원"},
            {"internal_number":"list_only_person","proposer_type_list":"의원","proposer_type":None},
        ]
        relationships=[{"internal_number":x["internal_number"],"person_name":"김가나다"} for x in bills]
        personal,quarantine=partition_bill_proposer_rows(bills,relationships)
        self.assertEqual([x["internal_number"] for x in personal],["matching_person","list_only_person"])
        self.assertEqual([x["internal_number"] for x in quarantine],["institution_list","institution_detail"])
        self.assertEqual(personal+quarantine,relationships[2:]+relationships[:2])

    def test_unknown_bill_reference_fails_closed(self):
        with self.assertRaises(ValueError):
            partition_bill_proposer_rows([], [{"internal_number":"missing"}])
    def test_duplicate_bill_reference_fails_closed(self):
        with self.assertRaises(ValueError):
            partition_bill_proposer_rows([{"internal_number":"x"},{"internal_number":"x"}],[])
if __name__=="__main__":
    unittest.main()
