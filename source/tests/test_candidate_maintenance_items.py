"""K5 consumable candidates remain scoped and visibly provisional."""

import unittest

from chageun.services.management import evaluate_management
from chageun.services.rule_registry import candidate_rules_for


AS_OF_DATE = "2026-10-15"
VEHICLE = {
    "id": 1,
    "manufacturer": "기아",
    "model": "K5",
    "generation": "DL3",
    "year": 2021,
    "engine": "G2.0 CVVL",
    "fuel": "가솔린",
    "transmission": "자동",
    "mileage": 90_000,
    "reference_date": AS_OF_DATE,
    "conditions": "normal",
}


class CandidateMaintenanceItemTests(unittest.TestCase):
    def selected_rules(self, vehicle=VEHICLE):
        return {
            rule["item_key"]: rule
            for rule in candidate_rules_for(vehicle)
            if rule["item_key"] in {"brake-fluid", "cabin-air-filter"}
        }

    def test_normal_candidates_include_brake_fluid_and_cabin_filter(self):
        rules = self.selected_rules()
        self.assertEqual(set(rules), {"brake-fluid", "cabin-air-filter"})
        self.assertEqual(rules["brake-fluid"]["interval_km"], 50_000)
        self.assertEqual(rules["cabin-air-filter"]["interval_km"], 15_000)

    def test_unknown_history_at_90000km_is_a_check_prompt_not_a_claim_of_missed_service(self):
        for item_key, first_mileage in (("brake-fluid", 50_000), ("cabin-air-filter", 15_000)):
            with self.subTest(item_key=item_key):
                rule = self.selected_rules()[item_key]
                result = evaluate_management(VEHICLE, [], rule, AS_OF_DATE)
                self.assertEqual(result["history_status"], "unknown")
                self.assertEqual(result["timing_status"], "due")
                self.assertEqual(result["next_mileage"], first_mileage)
                self.assertIn("이력 미확인", result["labels"])
                self.assertIn("지금 확인할 항목", result["labels"])
                self.assertTrue(result["rights_review_pending"])
                self.assertEqual(result["rights_status_label"], "사용 권리 확인 중")
                self.assertIn("마지막", result["questions"][0])

    def test_brake_fluid_replacement_history_moves_the_next_distance_interval(self):
        rule = self.selected_rules()["brake-fluid"]
        record = {
            "vehicle_id": 1,
            "kind": "previous_history",
            "item_key": "brake-fluid",
            "work_type": "replacement",
            "date": "2025-10-01",
            "mileage": 60_000,
        }
        result = evaluate_management(VEHICLE, [record], rule, AS_OF_DATE)
        self.assertEqual(result["history_status"], "recorded")
        self.assertEqual(result["timing_status"], "upcoming")
        self.assertEqual(result["next_mileage"], 110_000)
        self.assertIsNone(result["next_date"])

    def test_severe_cabin_filter_uses_condition_check_without_a_fixed_interval(self):
        severe_vehicle = {**VEHICLE, "conditions": "severe"}
        rules = self.selected_rules(severe_vehicle)
        rule = rules["cabin-air-filter"]
        self.assertTrue(rule["condition_based"])
        result = evaluate_management(severe_vehicle, [], rule, AS_OF_DATE)
        self.assertEqual(result["timing_status"], "unknown")
        self.assertIsNone(result["next_mileage"])
        self.assertIsNone(result["interval_km"])
        self.assertTrue(result["rights_review_pending"])

    def test_severe_brake_fluid_does_not_reuse_the_normal_fixed_interval(self):
        severe_vehicle = {**VEHICLE, "conditions": "severe"}
        rule = self.selected_rules(severe_vehicle)["brake-fluid"]
        result = evaluate_management(severe_vehicle, [], rule, AS_OF_DATE)
        self.assertTrue(rule["condition_based"])
        self.assertEqual(result["timing_status"], "unknown")
        self.assertIsNone(result["interval_km"])
        self.assertTrue(any("별도" in reason for reason in result["reasons"]))
        self.assertTrue(result["rights_review_pending"])

    def test_k5_candidates_do_not_apply_to_other_years_or_generations(self):
        for change in ({"year": 2022}, {"generation": "JF"}):
            with self.subTest(change=change):
                vehicle = {**VEHICLE, **change}
                self.assertEqual(self.selected_rules(vehicle), {})


if __name__ == "__main__":
    unittest.main()
