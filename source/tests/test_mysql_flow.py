"""전용 MySQL에서 실제 저장·재로그인·관리판단·계정 격리를 확인합니다."""

import copy
import json
from pathlib import Path
import secrets
import unittest
from datetime import datetime, timezone

from chageun import create_app
import test_api as support


@unittest.skipUnless(support.MYSQL_TESTS_ENABLED, "전용 시험 MySQL 설정이 필요합니다.")
class MySqlRecordFlowTests(unittest.TestCase):
    def setUp(self):
        self.config = support._prepare_mysql_test()
        self.app = create_app({"TESTING": True, "CHAGEUN_SERVER_MODE": True,
                               "SECRET_KEY": support.TEST_SECRET, **self.config})
        self.usernames = ["flow_" + secrets.token_hex(6), "flow_" + secrets.token_hex(6)]
        self.addCleanup(self.remove_test_users)
        self.clients = []
        for username in self.usernames:
            client = self.app.test_client()
            self.assertEqual(self.write(client, "/api/auth/register", {"username": username, "password": "test-only-password"}).status_code, 201)
            self.assertEqual(self.write(client, "/api/auth/login", {"username": username, "password": "test-only-password"}).status_code, 200)
            self.clients.append(client)
        self.fixture = json.loads((Path(__file__).parent / "fixtures/management.json").read_text(encoding="utf-8"))
        vehicle = copy.deepcopy(self.fixture["input"]["vehicle"])
        vehicle.pop("id"); vehicle.pop("created_at")
        response = self.write(self.clients[0], "/api/vehicles", vehicle)
        self.assertEqual(response.status_code, 201)
        self.vehicle_id = response.get_json()["data"]["id"]
        self.path = f"/api/vehicles/{self.vehicle_id}"

    def remove_test_users(self):
        connection = support._mysql_test_connect(self.config)
        try:
            with connection.cursor() as cursor:
                for username in self.usernames:
                    cursor.execute("DELETE FROM users WHERE username = %s", (username,))
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def write(client, path, payload=None):
        token = client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        return client.post(path, json=payload, headers={"X-CSRF-Token": token})

    @staticmethod
    def write_method(client, method, path, payload=None):
        token = client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        return getattr(client, method)(path, json=payload, headers={"X-CSRF-Token": token})

    def replacement(self):
        record = self.fixture["input"]["records"][0]
        return {key: value for key, value in record.items() if key not in ("id", "vehicle_id", "created_at")}

    def test_real_mysql_persistence_pagination_and_account_isolation(self):
        client, other = self.clients
        for work_type, record_date, mileage in (("replacement", "2026-01-31", 0),
                                                ("inspection", "2026-02-01", None), ("unknown", None, None)):
            response = self.write(client, self.path + "/records", {**self.replacement(), "work_type": work_type,
                                                                  "date": record_date, "mileage": mileage})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.get_json()["data"]["mileage"], mileage)
        self.assertEqual(self.write(client, "/api/auth/logout").status_code, 200)
        self.assertEqual(client.get(self.path + "/records").status_code, 401)
        self.assertEqual(self.write(client, "/api/auth/login", {"username": self.usernames[0], "password": "test-only-password"}).status_code, 200)
        first = client.get(self.path + "/records?page_size=2").get_json()
        second = client.get(self.path + "/records?page=2&page_size=2").get_json()
        self.assertEqual([row["work_type"] for row in first["data"]], ["inspection", "replacement"])
        self.assertEqual(second["data"][0]["work_type"], "unknown")
        self.assertEqual(first["meta"]["pagination"]["total"], 3)
        created = datetime.fromisoformat(first["data"][0]["created_at"].replace("Z", "+00:00"))
        self.assertLess(abs((datetime.now(timezone.utc) - created).total_seconds()), 60)
        self.assertEqual(other.get(self.path + "/records").status_code, 404)
        self.assertEqual(self.write(other, self.path + "/records", self.replacement()).status_code, 404)
        self.assertEqual(other.get(self.path + "/management").status_code, 404)
        item = client.get(self.path + "/management").get_json()["data"]["items"][0]
        self.assertEqual(item["history_status"], "recorded")
        self.assertEqual(item["timing_status"], "unknown")

    def test_real_mysql_management_uses_replacement_not_inspection(self):
        self.app.config.update(CHAGEUN_ALLOW_TEST_FIXTURE=True,
                               CHAGEUN_MANAGEMENT_AS_OF_DATE=self.fixture["input"]["as_of_date"])
        client = self.clients[0]
        self.assertEqual(self.write(client, self.path + "/records", self.replacement()).status_code, 201)
        self.assertEqual(self.write(client, self.path + "/records", {**self.replacement(), "work_type": "inspection",
                                                                    "date": "2026-05-01", "mileage": 25000}).status_code, 201)
        body = client.get(self.path + "/management").get_json()
        self.assertEqual(body["meta"]["calculation_mode"], "test_fixture")
        item = body["data"]["items"][0]
        self.assertEqual(item["next_mileage"], 30000)
        self.assertEqual(item["next_date"], "2026-07-31")
        self.assertTrue(item["is_fixture"])

    def test_real_mysql_record_edit_and_delete_persist_with_account_ownership(self):
        client, other = self.clients
        path = self.path + "/records"
        created = self.write(client, path, self.replacement()).get_json()["data"]
        record_path = f"/api/records/{created['id']}"
        updated = self.write_method(client, "patch", record_path,
                                    {"work_type": "inspection", "date": None, "mileage": 0}).get_json()["data"]
        self.assertEqual(updated["work_type"], "inspection")
        self.assertIsNone(updated["date"])
        self.assertEqual(updated["mileage"], 0)
        self.assertEqual(client.get(path).get_json()["data"][0], updated)
        self.assertEqual(self.write_method(other, "patch", record_path, {"result": "다른 계정"}).status_code, 404)
        self.assertEqual(self.write_method(other, "delete", record_path).status_code, 404)
        deleted = self.write_method(client, "delete", record_path)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(client.get(path).get_json()["data"], [])
        self.assertEqual(self.write_method(client, "delete", record_path).status_code, 404)
