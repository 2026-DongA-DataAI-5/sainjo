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
            if rule["item_key"] in {"brake-fluid", "cabin-air-filter", "coolant", "spark-plugs"}
        }

    def test_normal_candidates_include_brake_fluid_cabin_filter_coolant_and_spark_plugs(self):
        rules = self.selected_rules()
        self.assertEqual(set(rules), {"brake-fluid", "cabin-air-filter", "coolant", "spark-plugs"})
        self.assertEqual(rules["brake-fluid"]["interval_km"], 50_000)
        self.assertEqual(rules["cabin-air-filter"]["interval_km"], 15_000)
        self.assertEqual(rules["spark-plugs"]["first_interval_km"], 165_000)
        self.assertEqual(rules["spark-plugs"]["interval_km"], 165_000)
        self.assertEqual(rules["coolant"]["first_interval_km"], 200_000)
        self.assertEqual(rules["coolant"]["first_interval_months"], 120)
        self.assertEqual(rules["coolant"]["interval_km"], 40_000)
        self.assertEqual(rules["coolant"]["interval_months"], 24)

    def test_coolant_without_history_at_90000km_uses_first_mileage_and_date_baselines(self):
        rule = self.selected_rules()["coolant"]
        vehicle = {**VEHICLE, "in_service_date": "2021-10-15"}
        result = evaluate_management(vehicle, [], rule, AS_OF_DATE)
        self.assertEqual(result["history_status"], "unknown")
        self.assertEqual(result["timing_status"], "upcoming")
        self.assertEqual(result["next_mileage"], 200_000)
        self.assertEqual(result["next_date"], "2031-10-15")
        self.assertIn("이력 미확인", result["labels"])
        self.assertIn("향후 관리 예정", result["labels"])
        self.assertTrue(result["rights_review_pending"])

    def test_coolant_without_in_service_date_keeps_time_axis_partial(self):
        rule = self.selected_rules()["coolant"]
        result = evaluate_management(VEHICLE, [], rule, AS_OF_DATE)
        self.assertEqual(result["history_status"], "unknown")
        self.assertEqual(result["timing_status"], "partial")
        self.assertEqual(result["next_mileage"], 200_000)
        self.assertIsNone(result["next_date"])
        self.assertIn("vehicle.in_service_date", result["missing_fields"])
        self.assertIn("이력 미확인", result["labels"])

    def test_coolant_first_time_interval_is_due_when_ten_year_boundary_arrives(self):
        rule = self.selected_rules()["coolant"]
        vehicle = {
            **VEHICLE,
            "mileage": 150_000,
            "reference_date": "2031-10-15",
            "in_service_date": "2021-10-15",
        }
        result = evaluate_management(vehicle, [], rule, "2031-10-15")
        self.assertEqual(result["timing_status"], "due")
        self.assertEqual(result["next_mileage"], 200_000)
        self.assertEqual(result["next_date"], "2031-10-15")

    def test_coolant_replacement_restarts_both_recurring_intervals(self):
        rule = self.selected_rules()["coolant"]
        record = {
            "vehicle_id": 1,
            "kind": "previous_history",
            "item_key": "coolant",
            "work_type": "replacement",
            "date": "2025-10-15",
            "mileage": 80_000,
        }
        result = evaluate_management(VEHICLE, [record], rule, AS_OF_DATE)
        self.assertEqual(result["history_status"], "recorded")
        self.assertEqual(result["timing_status"], "upcoming")
        self.assertEqual(result["next_mileage"], 120_000)
        self.assertEqual(result["next_date"], "2027-10-15")
        self.assertTrue(result["rights_review_pending"])

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

    def test_severe_coolant_does_not_reuse_the_normal_replacement_interval(self):
        severe_vehicle = {**VEHICLE, "conditions": "severe"}
        rule = self.selected_rules(severe_vehicle)["coolant"]
        result = evaluate_management(severe_vehicle, [], rule, AS_OF_DATE)
        self.assertTrue(rule["condition_based"])
        self.assertEqual(result["timing_status"], "unknown")
        self.assertIsNone(result["interval_km"])
        self.assertTrue(any("가혹조건" in reason for reason in result["reasons"]))
        self.assertTrue(result["rights_review_pending"])

    def test_engine_air_cleaner_exposes_separate_normal_inspection_and_replacement_schedules(self):
        rules = [rule for rule in candidate_rules_for(VEHICLE) if rule["item_key"] == "air-filter"]
        self.assertEqual({rule["action"] for rule in rules}, {"inspection", "replacement"})
        by_action = {rule["action"]: rule for rule in rules}
        self.assertEqual(by_action["inspection"]["first_interval_km"], 10_000)
        self.assertEqual(by_action["inspection"]["interval_km"], 10_000)
        self.assertEqual(by_action["replacement"]["first_interval_km"], 40_000)
        self.assertEqual(by_action["replacement"]["interval_km"], 40_000)
        self.assertTrue(by_action["inspection"]["replacement_resets_inspection"])
        self.assertTrue(all(rule["rights_status"] == "pending_confirmation" for rule in rules))

    def test_engine_air_cleaner_history_resets_only_its_matching_schedule(self):
        vehicle = {**VEHICLE, "mileage": 30_000}
        rules = [rule for rule in candidate_rules_for(vehicle) if rule["item_key"] == "air-filter"]
        inspection = next(rule for rule in rules if rule["action"] == "inspection")
        replacement = next(rule for rule in rules if rule["action"] == "replacement")
        records = [{
            "vehicle_id": 1, "kind": "previous_history", "item_key": "air-filter",
            "work_type": "inspection", "date": "2026-01-01", "mileage": 20_000,
        }]
        check_result = evaluate_management(vehicle, records, inspection, AS_OF_DATE)
        replace_result = evaluate_management(vehicle, records, replacement, AS_OF_DATE)
        self.assertEqual(check_result["next_mileage"], 30_000)
        self.assertEqual(check_result["timing_status"], "due")
        self.assertEqual(replace_result["next_mileage"], 40_000)
        self.assertEqual(replace_result["timing_status"], "upcoming")

    def test_engine_air_cleaner_replacement_also_restarts_inspection_schedule(self):
        vehicle = {**VEHICLE, "mileage": 90_000}
        rules = [rule for rule in candidate_rules_for(vehicle) if rule["item_key"] == "air-filter"]
        inspection = next(rule for rule in rules if rule["action"] == "inspection")
        replacement = next(rule for rule in rules if rule["action"] == "replacement")
        records = [{
            "vehicle_id": 1, "kind": "previous_history", "item_key": "air-filter",
            "work_type": "replacement", "date": "2026-01-01", "mileage": 80_000,
        }]
        check_result = evaluate_management(vehicle, records, inspection, AS_OF_DATE)
        replace_result = evaluate_management(vehicle, records, replacement, AS_OF_DATE)
        self.assertEqual(check_result["next_mileage"], 90_000)
        self.assertEqual(check_result["timing_status"], "due")
        self.assertEqual(replace_result["next_mileage"], 120_000)
        self.assertEqual(replace_result["timing_status"], "upcoming")

    def test_engine_air_cleaner_candidates_do_not_apply_to_severe_conditions(self):
        severe_vehicle = {**VEHICLE, "conditions": "severe"}
        self.assertFalse(any(rule["item_key"] == "air-filter" for rule in candidate_rules_for(severe_vehicle)))

    def test_item_specific_severe_rules_require_matching_manual_condition_codes(self):
        dusty_vehicle = {**VEHICLE, "conditions": "severe", "severe_condition_codes": [2]}
        dusty_rules = candidate_rules_for(dusty_vehicle)
        self.assertTrue(any(rule["item_key"] == "air-filter" for rule in dusty_rules))
        self.assertFalse(any(rule["item_key"] == "spark-plugs" for rule in dusty_rules))

        short_trip_vehicle = {**VEHICLE, "conditions": "severe", "severe_condition_codes": [1]}
        short_trip_rules = candidate_rules_for(short_trip_vehicle)
        self.assertTrue(any(rule["item_key"] == "spark-plugs" for rule in short_trip_rules))
        self.assertFalse(any(rule["item_key"] == "air-filter" for rule in short_trip_rules))

    def test_k5_candidates_do_not_apply_to_other_years_or_generations(self):
        for change in ({"year": 2022}, {"generation": "JF"}):
            with self.subTest(change=change):
                vehicle = {**VEHICLE, **change}
                self.assertEqual(self.selected_rules(vehicle), {})

    def test_severe_engine_oil_requires_a_selected_manual_code_and_uses_the_matching_interval(self):
        severe_vehicle = {**VEHICLE, "conditions": "severe"}
        self.assertFalse(any(
            rule["item_key"] == "engine-oil" for rule in candidate_rules_for(severe_vehicle)
        ))

        oil_record = {
            "vehicle_id": 1,
            "kind": "previous_history",
            "item_key": "engine-oil",
            "work_type": "replacement",
            "date": "2026-02-01",
            "mileage": 80_000,
        }
        for code in range(1, 13):
            with self.subTest(severe_condition_code=code):
                vehicle = {**severe_vehicle, "severe_condition_codes": [code]}
                rules = [rule for rule in candidate_rules_for(vehicle) if rule["item_key"] == "engine-oil"]
                self.assertEqual(len(rules), 1)
                rule = rules[0]
                self.assertEqual(rule["interval_km"], 7_500)
                self.assertEqual(rule["interval_months"], 6)
                self.assertEqual(rule["matched_severe_condition_codes"], [code])
                self.assertEqual(rule["rights_status"], "pending_confirmation")

                result = evaluate_management(vehicle, [oil_record], rule, AS_OF_DATE)
                self.assertEqual(result["next_mileage"], 87_500)
                self.assertEqual(result["next_date"], "2026-08-01")
                self.assertEqual(result["matched_severe_condition_codes"], [code])
                self.assertIn("지금 확인할 항목", result["labels"])
                self.assertTrue(result["rights_review_pending"])

if __name__ == "__main__":
    unittest.main()
