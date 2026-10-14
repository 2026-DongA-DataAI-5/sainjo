"""기록 API의 소유권·검증·응답 계약. 실제 저장 시험은 test_mysql_flow.py에서 수행합니다."""

import copy
from datetime import date, datetime
from types import SimpleNamespace
import unittest
from unittest import mock

from chageun import create_app
from test_api import FakeVehicles, VALID_VEHICLE


VALID_RECORD = {
    "kind": "maintenance_result", "item_key": "engine-oil", "component_position": "unknown", "work_type": "replacement",
    "date": "2026-01-31", "mileage": 0, "result": "unknown", "source": None, "checked_date": None,
}


class FakeRecords:
    def __init__(self):
        self.rows = []

    def create_record(self, vehicle_id, values):
        row = {**values, "id": len(self.rows) + 1, "vehicle_id": vehicle_id,
               "created_at": datetime(2026, 10, 14, 0, 0, len(self.rows))}
        self.rows.append(row)
        return row["id"]

    def all_records(self, vehicle_id):
        return sorted([row for row in self.rows if row["vehicle_id"] == vehicle_id],
                      key=lambda row: (row["record_date"] or date.min, row["created_at"], row["id"]), reverse=True)

    def list_records_by_vehicle(self, vehicle_id, page, page_size):
        return self.all_records(vehicle_id)[(page - 1) * page_size:page * page_size]

    def count_records(self, vehicle_id):
        return len(self.all_records(vehicle_id))

    def find_record_by_id_and_vehicle(self, record_id, vehicle_id):
        return next((row for row in self.rows if row["id"] == record_id and row["vehicle_id"] == vehicle_id), None)

    def find_record_by_id_and_owner(self, record_id, owner_id, vehicles):
        row = next((row for row in self.rows if row["id"] == record_id), None)
        if row is None or vehicles.by_id_and_owner(row["vehicle_id"], owner_id) is None:
            return None
        return row

    def update_record(self, record_id, owner_id, values, vehicles):
        row = self.find_record_by_id_and_owner(record_id, owner_id, vehicles)
        if row is None:
            return 0
        row.update(values)
        return 1

    def delete_record(self, record_id, owner_id, vehicles):
        row = self.find_record_by_id_and_owner(record_id, owner_id, vehicles)
        if row is None:
            return 0
        self.rows.remove(row)
        return 1


class RecordsApiTests(unittest.TestCase):
    def setUp(self):
        self.vehicles = FakeVehicles()
        self.vehicle_id = self.vehicles.create(1, copy.deepcopy(VALID_VEHICLE))
        self.records = FakeRecords()
        self.db = mock.MagicMock()
        self.patchers = [
            mock.patch("chageun.api.vehicles.find_vehicle_by_id_and_owner", side_effect=self.vehicles.by_id_and_owner),
            mock.patch("chageun.api.get_db", return_value=self.db),
            mock.patch("chageun.api.records", new=SimpleNamespace(
                create_record=self.records.create_record,
                list_records_by_vehicle=self.records.list_records_by_vehicle,
                count_records=self.records.count_records,
                find_record_by_id_and_vehicle=self.records.find_record_by_id_and_vehicle,
                find_record_by_id_and_owner=lambda record_id, owner_id: self.records.find_record_by_id_and_owner(record_id, owner_id, self.vehicles),
                update_record=lambda record_id, owner_id, values: self.records.update_record(record_id, owner_id, values, self.vehicles),
                delete_record=lambda record_id, owner_id: self.records.delete_record(record_id, owner_id, self.vehicles),
                list_records_for_management=self.records.all_records,
            ), create=True),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app = create_app({"TESTING": True, "CHAGEUN_SERVER_MODE": True, "SECRET_KEY": "records-test-only"})
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
        self.path = f"/api/vehicles/{self.vehicle_id}/records"

    def post(self, payload=None, client=None):
        client = client or self.client
        token = client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        return client.post(self.path, json=VALID_RECORD if payload is None else payload,
                           headers={"X-CSRF-Token": token})

    def write_record(self, client, method, path, payload=None, csrf=True):
        token = client.get("/api/auth/csrf").get_json()["data"]["csrf_token"] if csrf else None
        headers = {"X-CSRF-Token": token} if token else {}
        return getattr(client, method)(path, json=payload, headers=headers)

    def test_create_and_list_preserve_zero_null_and_text(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        data = response.get_json()["data"]
        self.assertEqual(data["mileage"], 0)
        self.assertIsNone(data["source"])
        self.assertEqual(data["result"], "unknown")
        self.assertEqual(data["date"], VALID_RECORD["date"])
        self.assertTrue(data["created_at"].endswith("Z"))
        self.assertNotIn("record_date", data)
        self.assertNotIn("owner_id", data)
        listed = self.client.get(self.path).get_json()
        self.assertEqual(listed["data"], [data])
        self.assertEqual(listed["meta"]["pagination"], {"page": 1, "page_size": 20, "total": 1})
        self.assertEqual(listed["meta"]["mode"], "live")

    def test_anonymous_requests_are_401_before_csrf(self):
        client = self.app.test_client()
        self.assertEqual(client.get(self.path).status_code, 401)
        self.assertEqual(client.post(self.path, json=VALID_RECORD).status_code, 401)

    def test_csrf_failure_does_not_create_record(self):
        self.assertEqual(self.client.post(self.path, json=VALID_RECORD).status_code, 403)
        self.assertEqual(self.client.post(self.path, json=VALID_RECORD, headers={"X-CSRF-Token": "wrong"}).status_code, 403)
        self.assertEqual(self.records.rows, [])

    def test_other_account_and_missing_vehicle_have_same_404(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 2
        for method in ("get", "post"):
            if method == "post":
                token = client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
                kwargs = {"json": VALID_RECORD, "headers": {"X-CSRF-Token": token}}
            else:
                kwargs = {}
            other = getattr(client, method)(self.path, **kwargs)
            missing = getattr(client, method)("/api/vehicles/999/records", **kwargs)
            self.assertEqual(other.status_code, 404)
            self.assertEqual(other.get_json(), missing.get_json())

    def test_all_three_work_types_and_nullable_omissions(self):
        for work_type in ("inspection", "replacement", "unknown"):
            response = self.post({"kind": "previous_history", "item_key": "engine-oil", "work_type": work_type})
            self.assertEqual(response.status_code, 201)
            data = response.get_json()["data"]
            self.assertEqual(data["work_type"], work_type)
            self.assertEqual(data["component_position"], "unknown")
            for field in ("date", "mileage", "result", "source", "checked_date"):
                self.assertIsNone(data[field])

    def test_invalid_fields_are_400_without_saving(self):
        cases = [("mileage", True), ("mileage", "10"), ("mileage", -1), ("mileage", 1.2),
                 ("mileage", 1000001), ("date", "2026-02-30"), ("date", "2999-01-01"),
                 ("date", ""), ("checked_date", "2999-01-01"), ("work_type", None),
                 ("work_type", "fix"), ("kind", "question"), ("item_key", "coolant"),
                 ("source", " " * 2), ("result", "x" * 2001), ("source", "x" * 101),
                 ("vehicle_id", 999), ("created_at", "2026-01-01")]
        for field, value in cases:
            with self.subTest(field=field, value=str(value)[:30]):
                response = self.post({**VALID_RECORD, field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.get_json()["error"]["fields"])
        self.assertEqual(self.records.rows, [])

    def test_non_object_and_missing_required_are_400(self):
        for payload in ([], {}, {"kind": "maintenance_result"}):
            self.assertEqual(self.post(payload).status_code, 400)

    def test_pagination_orders_unknown_dates_last(self):
        for record_date in (None, "2026-01-01", "2026-03-01", "2026-03-01"):
            self.assertEqual(self.post({**VALID_RECORD, "date": record_date}).status_code, 201)
        first = self.client.get(self.path + "?page=1&page_size=2").get_json()
        second = self.client.get(self.path + "?page=2&page_size=2").get_json()
        self.assertEqual([row["id"] for row in first["data"]], [4, 3])
        self.assertEqual([row["id"] for row in second["data"]], [2, 1])
        self.assertEqual(first["meta"]["pagination"]["total"], 4)
        self.assertEqual(self.client.get(self.path + "?page=9").get_json()["data"], [])
        for query in ("page=0", "page=-1", "page=1.2", "page=true", "page_size=101", "page_size=0", "page=", "extra=1"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get(self.path + "?" + query).status_code, 400)

    def test_database_failure_rolls_back_and_hides_details(self):
        with mock.patch("chageun.api.records.create_record", side_effect=RuntimeError("PRIVATE_DB_DETAIL")):
            response = self.post()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("PRIVATE_DB_DETAIL", response.get_data(as_text=True))
        self.db.rollback.assert_called()

    def test_patch_updates_only_supplied_fields_and_persists_nulls(self):
        created = self.post().get_json()["data"]
        response = self.write_record(self.client, "patch", f"/api/records/{created['id']}",
                                     {"work_type": "inspection", "date": None, "source": "문서 대조"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["work_type"], "inspection")
        self.assertIsNone(data["date"])
        self.assertEqual(data["source"], "문서 대조")
        self.assertEqual(data["mileage"], 0)
        self.assertEqual(data["result"], "unknown")
        self.assertEqual(self.client.get(self.path).get_json()["data"][0], data)
        self.db.commit.assert_called()

    def test_patch_requires_csrf_and_rejects_unknown_or_invalid_fields(self):
        created = self.post().get_json()["data"]
        path = f"/api/records/{created['id']}"
        self.assertEqual(self.write_record(self.client, "patch", path, {"result": "수정"}, csrf=False).status_code, 403)
        for payload, field in (({"owner_id": 2}, "owner_id"), ({"date": "2999-01-01"}, "date"),
                               ({"work_type": "replace"}, "work_type")):
            with self.subTest(payload=payload):
                response = self.write_record(self.client, "patch", path, payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.get_json()["error"]["fields"])
        self.assertEqual(self.records.rows[0]["work_type"], "replacement")

    def test_patch_and_delete_hide_other_accounts_records(self):
        created = self.post().get_json()["data"]
        other = self.app.test_client()
        with other.session_transaction() as session:
            session["user_id"] = 2
        path = f"/api/records/{created['id']}"
        patched = self.write_record(other, "patch", path, {"result": "변경"})
        deleted = self.write_record(other, "delete", path)
        self.assertEqual(patched.status_code, 404)
        self.assertEqual(deleted.status_code, 404)
        self.assertEqual(self.records.rows[0]["result"], "unknown")

    def test_delete_requires_csrf_and_removes_record(self):
        created = self.post().get_json()["data"]
        path = f"/api/records/{created['id']}"
        self.assertEqual(self.write_record(self.client, "delete", path, csrf=False).status_code, 403)
        response = self.write_record(self.client, "delete", path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], {"id": created["id"], "deleted": True})
        self.assertEqual(self.client.get(self.path).get_json()["data"], [])
        self.assertEqual(self.write_record(self.client, "delete", path).status_code, 404)
