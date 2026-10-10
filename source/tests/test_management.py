"""Table-driven contract tests for the pure management engine."""

from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).parent
FIXTURE_PATH = TESTS_DIR / "fixtures" / "management.json"
MODULE_PATH = TESTS_DIR.parent / "chageun" / "services" / "management.py"
MODULE_SPEC = importlib.util.spec_from_file_location("management_under_test", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise ImportError(f"Could not load management module from {MODULE_PATH}")
MANAGEMENT_MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MANAGEMENT_MODULE)
evaluate_management = MANAGEMENT_MODULE.evaluate_management


def load_contract_case():
    with FIXTURE_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


class ManagementEngineTests(unittest.TestCase):
    def setUp(self):
        self.case = load_contract_case()

    def evaluate(self, *, vehicle=None, records=None, rule=None, as_of_date=None):
        data = self.case["input"]
        return evaluate_management(
            copy.deepcopy(data["vehicle"] if vehicle is None else vehicle),
            copy.deepcopy(data["records"] if records is None else records),
            copy.deepcopy(data["rule"] if rule is None else rule),
            data["as_of_date"] if as_of_date is None else as_of_date,
        )

    def test_fixed_contract_fixture(self):
        result = self.evaluate()
        for field in self.case["compare_fields"]:
            with self.subTest(field=field):
                self.assertEqual(result[field], self.case["expected"][field])
        self.assertEqual(result["reasons"], self.case["expected"]["reasons"])
        self.assertEqual(result["questions"], ["마지막 교환 기록과 운행조건을 함께 확인해 주실 수 있나요?"])

    def test_distance_boundary_is_due_inclusive(self):
        vehicle = copy.deepcopy(self.case["input"]["vehicle"])
        vehicle["mileage"] = 30_000
        result = self.evaluate(vehicle=vehicle)
        self.assertEqual(result["timing_status"], "due")
        self.assertEqual(result["next_mileage"], 30_000)
        self.assertIn("지금 확인할 항목", result["labels"])

    def test_date_boundary_is_due_inclusive(self):
        vehicle = copy.deepcopy(self.case["input"]["vehicle"])
        vehicle["reference_date"] = "2026-07-31"
        result = self.evaluate(vehicle=vehicle, as_of_date="2026-07-31")
        self.assertEqual(result["timing_status"], "due")
        self.assertEqual(result["next_date"], "2026-07-31")

    def test_one_day_before_date_boundary_is_upcoming(self):
        vehicle = copy.deepcopy(self.case["input"]["vehicle"])
        vehicle["reference_date"] = "2026-07-30"
        result = self.evaluate(vehicle=vehicle, as_of_date="2026-07-30")
        self.assertEqual(result["timing_status"], "upcoming")

    def test_month_addition_clamps_to_calendar_month_end(self):
        vehicle = copy.deepcopy(self.case["input"]["vehicle"])
        vehicle.update(mileage=0, reference_date="2026-02-27")
        records = copy.deepcopy(self.case["input"]["records"])
        records[0].update(date="2026-01-31", mileage=0)
        rule = copy.deepcopy(self.case["input"]["rule"])
        rule.update(interval_km=10_000, interval_months=1)

        before_due = self.evaluate(
            vehicle=vehicle, records=records, rule=rule, as_of_date="2026-02-27"
        )
        self.assertEqual(before_due["next_date"], "2026-02-28")
        self.assertEqual(before_due["timing_status"], "upcoming")

        vehicle["reference_date"] = "2026-02-28"
        at_due = self.evaluate(
            vehicle=vehicle, records=records, rule=rule, as_of_date="2026-02-28"
        )
        self.assertEqual(at_due["timing_status"], "due")

    def test_later_inspection_does_not_reset_replacement_threshold(self):
        records = copy.deepcopy(self.case["input"]["records"])
        inspection = copy.deepcopy(records[0])
        inspection.update(id=2, work_type="inspection", date="2026-05-01", mileage=24_000)
        records.append(inspection)
        result = self.evaluate(records=records)
        self.assertEqual(result["history_status"], "recorded")
        self.assertEqual(result["next_mileage"], 30_000)

    def test_undated_replacement_allows_distance_only_partial_result(self):
        vehicle = copy.deepcopy(self.case["input"]["vehicle"])
        records = copy.deepcopy(self.case["input"]["records"])
        records[0]["date"] = None
        result = self.evaluate(vehicle=vehicle, records=records)
        self.assertEqual(result["timing_status"], "partial")
        self.assertEqual(result["next_mileage"], 30_000)
        self.assertIsNone(result["next_date"])
        self.assertNotIn("향후 관리 예정", result["labels"])

    def test_no_history_and_inspection_only_do_not_create_schedule(self):
        no_history = self.evaluate(records=[])
        self.assertEqual(no_history["history_status"], "unknown")
        self.assertEqual(no_history["timing_status"], "unknown")
        self.assertIsNone(no_history["next_mileage"])

        inspection = copy.deepcopy(self.case["input"]["records"][0])
        inspection["work_type"] = "inspection"
        inspection_result = self.evaluate(records=[inspection])
        self.assertEqual(inspection_result["history_status"], "recorded")
        self.assertEqual(inspection_result["timing_status"], "unknown")
        self.assertIsNone(inspection_result["next_date"])

    def test_unknown_work_type_is_not_a_known_history(self):
        record = copy.deepcopy(self.case["input"]["records"][0])
        record["work_type"] = "unknown"
        result = self.evaluate(records=[record])
        self.assertEqual(result["history_status"], "unknown")

    def test_missing_or_invalid_vehicle_id_prevents_cross_vehicle_calculation(self):
        records = copy.deepcopy(self.case["input"]["records"])
        for vehicle_id in (None, 0, True, "1"):
            with self.subTest(vehicle_id=vehicle_id):
                vehicle = copy.deepcopy(self.case["input"]["vehicle"])
                if vehicle_id is None:
                    vehicle.pop("id")
                else:
                    vehicle["id"] = vehicle_id

                result = self.evaluate(vehicle=vehicle, records=records)

                self.assertEqual(result["history_status"], "unknown")
                self.assertEqual(result["timing_status"], "unknown")
                self.assertIn("vehicle.id", result["missing_fields"])
                self.assertIsNone(result["next_mileage"])
                self.assertIsNone(result["next_date"])

    def test_wrong_generation_engine_or_year_is_unsupported(self):
        for field, value in (("generation", "JF"), ("engine", "1.6 T-GDI"), ("year", 2024)):
            with self.subTest(field=field):
                vehicle = copy.deepcopy(self.case["input"]["vehicle"])
                vehicle[field] = value
                result = self.evaluate(vehicle=vehicle)
                self.assertEqual(result["timing_status"], "unsupported")
                self.assertIsNone(result["next_mileage"])
                self.assertIsNone(result["next_date"])

    def test_unknown_conditions_and_unapproved_rule_do_not_calculate(self):
        vehicle = copy.deepcopy(self.case["input"]["vehicle"])
        vehicle["conditions"] = "unknown"
        unknown_conditions = self.evaluate(vehicle=vehicle)
        self.assertEqual(unknown_conditions["timing_status"], "unknown")
        self.assertIn("vehicle.conditions", unknown_conditions["missing_fields"])

        rule = copy.deepcopy(self.case["input"]["rule"])
        rule["rights_status"] = "unknown"
        unapproved = self.evaluate(rule=rule)
        self.assertEqual(unapproved["timing_status"], "unknown")
        self.assertIsNone(unapproved["next_mileage"])

    def test_zero_mileage_is_not_treated_as_missing(self):
        vehicle = copy.deepcopy(self.case["input"]["vehicle"])
        vehicle.update(mileage=0, reference_date="2026-06-01")
        records = copy.deepcopy(self.case["input"]["records"])
        records[0]["mileage"] = 0
        result = self.evaluate(vehicle=vehicle, records=records)
        self.assertEqual(result["next_mileage"], 10_000)
        self.assertNotIn("vehicle.mileage", result["missing_fields"])

        vehicle["mileage"] = None
        missing = self.evaluate(vehicle=vehicle, records=records)
        self.assertIsNone(missing["next_mileage"])
        self.assertIn("vehicle.mileage", missing["missing_fields"])

    def test_stale_mileage_measurement_leaves_distance_axis_partial(self):
        vehicle = copy.deepcopy(self.case["input"]["vehicle"])
        vehicle["reference_date"] = "2026-05-31"
        result = self.evaluate(vehicle=vehicle)
        self.assertEqual(result["timing_status"], "partial")
        self.assertIsNone(result["next_mileage"])
        self.assertEqual(result["next_date"], "2026-07-31")

    def test_odometer_reversal_does_not_calculate_distance_axis(self):
        vehicle = copy.deepcopy(self.case["input"]["vehicle"])
        vehicle["mileage"] = 19_000
        result = self.evaluate(vehicle=vehicle)
        self.assertEqual(result["timing_status"], "partial")
        self.assertIsNone(result["next_mileage"])
        self.assertEqual(result["next_date"], "2026-07-31")

    def test_conflicting_replacement_order_prevents_using_a_latest_record(self):
        records = copy.deepcopy(self.case["input"]["records"])
        later = copy.deepcopy(records[0])
        later.update(id=2, date="2026-03-01", mileage=19_000)
        records.append(later)
        result = self.evaluate(records=records)
        self.assertEqual(result["timing_status"], "unknown")
        self.assertIsNone(result["next_mileage"])
        self.assertIsNone(result["next_date"])

    def test_same_day_replacements_with_different_mileage_are_ambiguous(self):
        records = copy.deepcopy(self.case["input"]["records"])
        duplicate_day = copy.deepcopy(records[0])
        duplicate_day.update(id=2, mileage=21_000)
        records.append(duplicate_day)
        result = self.evaluate(records=records)
        self.assertEqual(result["timing_status"], "unknown")
        self.assertIsNone(result["next_mileage"])
        self.assertIsNone(result["next_date"])

    def test_created_at_is_not_used_as_maintenance_date_or_order(self):
        records = copy.deepcopy(self.case["input"]["records"])
        records[0].update(date=None, mileage=20_000)
        # A newer created_at does not resolve the missing maintenance date.
        records[0]["created_at"] = "2026-06-01T00:00:00Z"
        result = self.evaluate(records=records)
        self.assertEqual(result["timing_status"], "partial")
        self.assertIsNone(result["next_date"])

    def test_invalid_as_of_date_returns_contract_shaped_unknown(self):
        result = self.evaluate(as_of_date="2026-2-01")
        self.assertEqual(result["timing_status"], "unknown")
        self.assertIn("as_of_date", result["missing_fields"])
        self.assertEqual(
            set(result),
            {
                "item_key", "history_status", "timing_status", "labels", "next_mileage",
                "next_date", "reasons", "missing_fields", "rule_id", "source",
                "checked_date", "questions", "is_fixture",
            },
        )


if __name__ == "__main__":
    unittest.main()
