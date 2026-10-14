"""실제 기록과 순수 관리판단 엔진을 연결하는 API의 경계 시험."""

import copy
import json
from datetime import date
from pathlib import Path
import unittest
import test_records_api as support


class ManagementApiTests(unittest.TestCase):
    post = support.RecordsApiTests.post

    def setUp(self):
        support.RecordsApiTests.setUp(self)
        self.fixture = json.loads((Path(__file__).parent / "fixtures/management.json").read_text(encoding="utf-8"))
        vehicle = copy.deepcopy(self.fixture["input"]["vehicle"])
        vehicle["reference_date"] = date.fromisoformat(vehicle["reference_date"])
        self.vehicles.rows[0].update(vehicle)
        self.app.config["CHAGEUN_MANAGEMENT_AS_OF_DATE"] = self.fixture["input"]["as_of_date"]
        self.management_path = f"/api/vehicles/{self.vehicle_id}/management"

    def item(self):
        response = self.client.get(self.management_path)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["data"]["vehicle_id"], self.vehicle_id)
        items = body["data"]["items"]
        oil_item = next((item for item in items if item["item_key"] == "engine-oil"), None)
        self.assertIsNotNone(oil_item)
        return oil_item, body["meta"]

    def test_default_without_rule_does_not_calculate(self):
        item, meta = self.item()
        self.assertEqual(meta["calculation_mode"], "unavailable")
        self.assertEqual(item["timing_status"], "unknown")
        self.assertIsNone(item["next_mileage"])
        self.assertFalse(item["is_fixture"])
        self.assertEqual(item["rule_id"], "KIA_DL3_2021_G20_OIL_NORMAL_CANDIDATE")
        self.assertIn("rule.rights_status", item["missing_fields"])
        self.assertIn("권한 또는 검토 상태", item["reasons"][0])

    def test_known_history_is_preserved_without_rule(self):
        self.assertEqual(self.post({**support.VALID_RECORD, "work_type": "inspection"}).status_code, 201)
        item, meta = self.item()
        self.assertEqual(item["history_status"], "recorded")
        self.assertEqual(item["timing_status"], "unknown")
        self.assertEqual(meta["calculation_mode"], "unavailable")

    def test_candidate_rule_never_calculates_before_rights_approval(self):
        self.assertEqual(self.post({**support.VALID_RECORD, "date": "2026-01-01", "mileage": 10000}).status_code, 201)
        item, meta = self.item()
        self.assertEqual(meta["calculation_mode"], "unavailable")
        self.assertEqual(item["rule_id"], "KIA_DL3_2021_G20_OIL_NORMAL_CANDIDATE")
        self.assertEqual(item["timing_status"], "unknown")
        self.assertIsNone(item["next_mileage"])
        self.assertIsNone(item["next_date"])

    def test_only_verified_candidate_year_and_conditions_resolve(self):
        vehicle = self.vehicles.rows[0]
        vehicle["year"] = 2022
        item, _ = self.item()
        self.assertIsNone(item["rule_id"])
        self.assertIn("rule", item["missing_fields"])
        vehicle["year"] = 2021
        vehicle["conditions"] = "severe"
        item, _ = self.item()
        self.assertEqual(item["rule_id"], "KIA_DL3_2021_G20_OIL_SEVERE_CANDIDATE")

    def test_explicit_fixture_and_record_mapping_match_engine_contract(self):
        self.app.config["CHAGEUN_ALLOW_TEST_FIXTURE"] = True
        record = self.fixture["input"]["records"][0]
        payload = {key: value for key, value in record.items() if key not in ("id", "vehicle_id", "created_at")}
        self.assertEqual(self.post(payload).status_code, 201)
        item, meta = self.item()
        self.assertEqual(meta["calculation_mode"], "test_fixture")
        for field in self.fixture["compare_fields"]:
            self.assertEqual(item[field], self.fixture["expected"][field], field)

    def test_inspection_does_not_reset_replacement_or_unknown_history(self):
        self.app.config["CHAGEUN_ALLOW_TEST_FIXTURE"] = True
        self.post({**support.VALID_RECORD, "work_type": "unknown"})
        item, _ = self.item()
        self.assertEqual(item["history_status"], "unknown")
        self.post({**support.VALID_RECORD, "work_type": "inspection"})
        item, _ = self.item()
        self.assertEqual(item["history_status"], "recorded")
        self.assertEqual(item["timing_status"], "unknown")
        self.assertIsNone(item["next_date"])

    def test_jf_is_unsupported_and_unknown_conditions_are_unknown(self):
        self.app.config["CHAGEUN_ALLOW_TEST_FIXTURE"] = True
        self.vehicles.rows[0]["generation"] = "JF"
        self.assertEqual(self.item()[0]["timing_status"], "unsupported")
        self.vehicles.rows[0]["generation"] = "DL3"
        self.vehicles.rows[0]["conditions"] = "unknown"
        self.assertEqual(self.item()[0]["timing_status"], "unknown")

    def test_management_auth_and_ownership(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get(self.management_path).status_code, 401)
        with anonymous.session_transaction() as session:
            session["user_id"] = 2
        other = anonymous.get(self.management_path)
        missing = anonymous.get("/api/vehicles/999/management")
        self.assertEqual(other.status_code, 404)
        self.assertEqual(other.get_json(), missing.get_json())

    def test_brake_and_ball_joint_guidance_is_scoped_to_four_positions(self):
        response = self.client.get(self.management_path)
        items = response.get_json()["data"]["items"]
        for item_key in ("brake-pads-discs", "lower-arm-ball-joint"):
            scoped = [item for item in items if item["item_key"] == item_key]
            self.assertEqual(
                {item["component_position"] for item in scoped},
                {"front_left", "front_right", "rear_left", "rear_right"},
            )

    def test_brake_history_does_not_mark_the_opposite_corner_as_recorded(self):
        record = {
            **support.VALID_RECORD,
            "item_key": "brake-pads-discs",
            "component_position": "front_left",
            "work_type": "inspection",
            "date": "2026-01-01",
            "mileage": 10000,
        }
        self.assertEqual(self.post(record).status_code, 201)
        items = self.client.get(self.management_path).get_json()["data"]["items"]
        scoped = {item["component_position"]: item for item in items if item["item_key"] == "brake-pads-discs"}
        self.assertEqual(scoped["front_left"]["history_status"], "recorded")
        self.assertEqual(scoped["front_right"]["history_status"], "unknown")

    def test_unknown_brake_record_location_is_reported_as_missing_information(self):
        record = {
            **support.VALID_RECORD,
            "item_key": "brake-pads-discs",
            "component_position": "unknown",
            "work_type": "inspection",
            "date": "2026-01-01",
            "mileage": 10000,
        }
        self.assertEqual(self.post(record).status_code, 201)
        items = self.client.get(self.management_path).get_json()["data"]["items"]
        front_left = next(item for item in items if item["item_key"] == "brake-pads-discs" and item["component_position"] == "front_left")
        self.assertEqual(front_left["history_status"], "unknown")
        self.assertIn("record.component_position", front_left["missing_fields"])
