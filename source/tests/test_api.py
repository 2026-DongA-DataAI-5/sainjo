"""인증 API 1단계 시험.

- 기본 실행(DB 없이): users 저장소를 메모리 가짜 객체로 바꿔 규약(CSRF, 401/403, 입력 검증, 오류 형식)을 검사합니다.
- MySQL 실행: CHAGEUN_MYSQL_DATABASE 등 시험 DB 환경변수를 설정했을 때만 실제 저장·재로그인을 검사합니다.
  반드시 시험 DB를 지정하세요. 실제 사용자 DB를 가리키면 안 됩니다.

실행(source 폴더에서):
    .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -p "test_api*.py"
"""

import os
import secrets
import unittest
from datetime import date
from unittest import mock

import pymysql
from werkzeug.security import generate_password_hash

from chageun import create_app

TEST_SECRET = "unit-test-secret-only-not-for-deploy"

VEHICLE_FIELD_KEYS = {
    "id",
    "manufacturer",
    "model",
    "generation",
    "year",
    "engine",
    "fuel",
    "transmission",
    "mileage",
    "reference_date",
    "conditions",
}
VALID_VEHICLE = {
    "manufacturer": "현대",
    "model": "아반떼",
    "generation": "JF",
    "year": 2017,
    "engine": "1.6 GDI",
    "fuel": "가솔린",
    "transmission": "자동",
    "mileage": 0,
    "reference_date": "2026-10-01",
    "conditions": "normal",
}


class FakeUsers:
    """users 테이블을 흉내 내는 메모리 저장소. 중복 아이디는 MySQL과 같은 1062 오류를 냅니다."""

    def __init__(self):
        self.rows = {}
        self.next_id = 1

    def create(self, username, password_hash):
        if username in self.rows:
            raise pymysql.err.IntegrityError(1062, "Duplicate entry for key 'uq_users_username'")
        user_id = self.next_id
        self.next_id += 1
        self.rows[username] = {"id": user_id, "username": username, "password_hash": password_hash}
        return user_id

    def by_username(self, username):
        return self.rows.get(username)

    def by_id(self, user_id):
        for row in self.rows.values():
            if row["id"] == user_id:
                return {"id": row["id"], "username": row["username"]}
        return None


class AuthApiTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeUsers()
        self.db = mock.MagicMock()
        self.create_mock = mock.patch(
            "chageun.api.users.create_user", side_effect=self.fake.create
        ).start()
        self.addCleanup(mock.patch.stopall)
        mock.patch("chageun.api.get_db", return_value=self.db).start()
        mock.patch(
            "chageun.api.users.find_user_by_username", side_effect=self.fake.by_username
        ).start()
        mock.patch("chageun.api.users.find_user_by_id", side_effect=self.fake.by_id).start()

        app = create_app({"TESTING": True, "CHAGEUN_SERVER_MODE": True, "SECRET_KEY": TEST_SECRET})
        self.client = app.test_client()

    def csrf(self):
        response = self.client.get("/api/auth/csrf")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["data"]["csrf_token"]

    def post(self, path, body=None, token=None):
        headers = {} if token is None else {"X-CSRF-Token": token}
        return self.client.post(path, json=body, headers=headers)

    def register(self, username="tester_a", password="correct-horse"):
        return self.post(
            "/api/auth/register", {"username": username, "password": password}, self.csrf()
        )

    def login(self, username="tester_a", password="correct-horse"):
        return self.post("/api/auth/login", {"username": username, "password": password}, self.csrf())

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        body = response.get_json()
        self.assertEqual(body["error"]["code"], code)
        self.assertIsInstance(body["error"]["fields"], dict)
        self.assertEqual(body["meta"]["contract_version"], "1.0")
        return body

    def test_csrf_endpoint_returns_token_in_envelope(self):
        response = self.client.get("/api/auth/csrf")
        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["data"]["csrf_token"])
        self.assertEqual(body["meta"]["contract_version"], "1.0")
        self.assertEqual(body["meta"]["mode"], "live")
        self.assertEqual(body["meta"]["calculation_mode"], "none")

    def test_register_without_csrf_is_403(self):
        response = self.post("/api/auth/register", {"username": "tester_a", "password": "correct-horse"})
        self.assert_error(response, 403, "CSRF_FAILED")
        self.assertEqual(self.fake.rows, {})

    def test_register_with_wrong_or_non_ascii_csrf_is_403_not_500(self):
        self.csrf()
        for token in ["wrong-token", "한글토큰"]:
            response = self.post(
                "/api/auth/register", {"username": "tester_a", "password": "correct-horse"}, token
            )
            self.assert_error(response, 403, "CSRF_FAILED")

    def test_register_success_returns_201_without_secrets_and_no_auto_login(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        data = response.get_json()["data"]
        self.assertEqual(data, {"id": 1, "username": "tester_a"})
        self.assertNotIn("password", response.get_data(as_text=True))
        self.assertNotIn("password_hash", response.get_data(as_text=True))
        # 가입만으로는 로그인되지 않습니다.
        self.assert_error(self.client.get("/api/auth/me"), 401, "AUTH_REQUIRED")
        # 저장된 값은 해시입니다.
        self.assertNotEqual(self.fake.rows["tester_a"]["password_hash"], "correct-horse")

    def test_register_duplicate_username_is_409(self):
        self.assertEqual(self.register().status_code, 201)
        response = self.register()
        body = self.assert_error(response, 409, "CONFLICT")
        self.assertIn("username", body["error"]["fields"])

    def test_register_rejects_invalid_username_and_password_with_field_errors(self):
        cases = [
            {"username": "Tester_A", "password": "correct-horse"},
            {"username": "ab", "password": "correct-horse"},
            {"username": "tester_a\n", "password": "correct-horse"},
            {"username": "tester_a", "password": "short"},
            {"username": "tester_a", "password": "x" * 129},
            {"username": "tester_a", "password": "correct-horse", "role": "admin"},
        ]
        for body in cases:
            with self.subTest(body=body):
                response = self.post("/api/auth/register", body, self.csrf())
                error = self.assert_error(response, 400, "VALIDATION_ERROR")
                self.assertTrue(error["error"]["fields"])
        self.assertEqual(self.fake.rows, {})

    def test_password_is_not_trimmed(self):
        response = self.register(password="  spaced-pass  ")
        self.assertEqual(response.status_code, 201)
        self.assert_error(self.login(password="spaced-pass"), 401, "INVALID_CREDENTIALS")
        self.assertEqual(self.login(password="  spaced-pass  ").status_code, 200)

    def test_non_object_json_is_400(self):
        response = self.post("/api/auth/register", ["tester_a", "correct-horse"], self.csrf())
        self.assert_error(response, 400, "VALIDATION_ERROR")

    def test_wrong_password_and_unknown_user_return_same_error(self):
        self.register()
        wrong_password = self.login(password="wrong-password-1")
        unknown_user = self.login(username="nobody_here")
        self.assert_error(wrong_password, 401, "INVALID_CREDENTIALS")
        self.assert_error(unknown_user, 401, "INVALID_CREDENTIALS")
        self.assertEqual(wrong_password.get_json()["error"]["message"], unknown_user.get_json()["error"]["message"])

    def test_login_me_logout_flow_and_token_regenerated(self):
        self.register()
        old_token = self.csrf()
        response = self.post("/api/auth/login", {"username": "tester_a", "password": "correct-horse"}, old_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], {"id": 1, "username": "tester_a"})

        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["data"], {"id": 1, "username": "tester_a"})

        # 로그인 후 이전 CSRF 토큰은 더 이상 유효하지 않습니다.
        self.assert_error(self.post("/api/auth/logout", None, old_token), 403, "CSRF_FAILED")

        new_token = self.csrf()
        self.assertNotEqual(new_token, old_token)
        logout = self.post("/api/auth/logout", None, new_token)
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(logout.get_json()["data"], {"logged_out": True})
        self.assert_error(self.client.get("/api/auth/me"), 401, "AUTH_REQUIRED")

    def test_me_without_login_is_401(self):
        self.assert_error(self.client.get("/api/auth/me"), 401, "AUTH_REQUIRED")

    def test_logout_without_login_is_401_even_without_csrf(self):
        self.assert_error(self.post("/api/auth/logout"), 401, "AUTH_REQUIRED")

    def test_logout_when_logged_in_without_csrf_is_403(self):
        self.register()
        self.login()
        self.assert_error(self.post("/api/auth/logout"), 403, "CSRF_FAILED")
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

    def test_database_error_is_500_and_hides_details(self):
        self.create_mock.side_effect = pymysql.err.OperationalError(
            2003, "Can't connect to MySQL server password=super-secret-value"
        )
        response = self.register()
        self.assert_error(response, 500, "INTERNAL_ERROR")
        text = response.get_data(as_text=True)
        self.assertNotIn("super-secret-value", text)
        self.assertNotIn("MySQL", text)
        self.db.rollback.assert_called()

    def test_unknown_api_route_is_404(self):
        response = self.client.post("/api/auth/does-not-exist", json={}, headers={"X-CSRF-Token": self.csrf()})
        self.assertEqual(response.status_code, 404)


@unittest.skipUnless(
    os.environ.get("CHAGEUN_TEST_MYSQL_DATABASE"),
    "시험 MySQL 환경변수(CHAGEUN_TEST_MYSQL_DATABASE 등)가 없어 실제 DB 시험을 건너뜁니다.",
)
class MySqlAuthPersistenceTest(unittest.TestCase):
    """실제 MySQL에서 가입 → 재로그인 → 조회가 유지되는지 확인합니다. 시험 DB에서만 실행하세요."""

    def setUp(self):
        self.app = create_app({"TESTING": True, "CHAGEUN_SERVER_MODE": True, "SECRET_KEY": TEST_SECRET})
        self.client = self.app.test_client()
        self.username = f"tester_{secrets.token_hex(4)}"
        self.password = "correct-horse-battery"

    def tearDown(self):
        config = self.app.config
        conn = pymysql.connect(
            host=config["MYSQL_HOST"],
            port=config["MYSQL_PORT"],
            user=config["MYSQL_USER"],
            password=config["MYSQL_PASSWORD"],
            database=config["MYSQL_DATABASE"],
            charset="utf8mb4",
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE username = %s", (self.username,))
            conn.commit()
        finally:
            conn.close()

    def csrf(self):
        return self.client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]

    def test_register_login_me_persist_across_new_client(self):
        token = self.csrf()
        register = self.client.post(
            "/api/auth/register",
            json={"username": self.username, "password": self.password},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(register.status_code, 201)

        # 새 클라이언트(= 재로그인에 해당)에서 다시 로그인합니다.
        other = self.app.test_client()
        token = other.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        login = other.post(
            "/api/auth/login",
            json={"username": self.username, "password": self.password},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(login.status_code, 200)
        me = other.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["data"]["username"], self.username)


class FakeVehicles:
    """vehicles 테이블을 흉내 내는 메모리 저장소. owner_id UNIQUE(1062)와 소유자 조건을 MySQL처럼 지킵니다."""

    def __init__(self):
        self.rows = []
        self.next_id = 1

    @staticmethod
    def _public(row):
        return {key: row[key] for key in VEHICLE_FIELD_KEYS}

    def create(self, owner_id, values):
        if any(row["owner_id"] == owner_id for row in self.rows):
            raise pymysql.err.IntegrityError(1062, "Duplicate entry for key 'uq_vehicles_owner'")
        row = {key: values[key] for key in VEHICLE_FIELD_KEYS - {"id"}}
        row["reference_date"] = date.fromisoformat(values["reference_date"]) if values["reference_date"] else None
        row.update({"id": self.next_id, "owner_id": owner_id})
        self.next_id += 1
        self.rows.append(row)
        return row["id"]

    def by_owner(self, owner_id):
        for row in self.rows:
            if row["owner_id"] == owner_id:
                return self._public(row)
        return None

    def by_id_and_owner(self, vehicle_id, owner_id):
        for row in self.rows:
            if row["id"] == vehicle_id and row["owner_id"] == owner_id:
                return self._public(row)
        return None


class VehicleApiTest(unittest.TestCase):
    def setUp(self):
        self.users = FakeUsers()
        self.vehicles = FakeVehicles()
        self.db = mock.MagicMock()
        mock.patch("chageun.api.users.create_user", side_effect=self.users.create).start()
        mock.patch("chageun.api.users.find_user_by_username", side_effect=self.users.by_username).start()
        mock.patch("chageun.api.users.find_user_by_id", side_effect=self.users.by_id).start()
        mock.patch("chageun.api.vehicles.create_vehicle", side_effect=self.vehicles.create).start()
        mock.patch("chageun.api.vehicles.find_vehicle_by_owner", side_effect=self.vehicles.by_owner).start()
        mock.patch(
            "chageun.api.vehicles.find_vehicle_by_id_and_owner", side_effect=self.vehicles.by_id_and_owner
        ).start()
        mock.patch("chageun.api.get_db", return_value=self.db).start()
        self.addCleanup(mock.patch.stopall)

        self.app = create_app({"TESTING": True, "CHAGEUN_SERVER_MODE": True, "SECRET_KEY": TEST_SECRET})
        self.users.create("tester_a", generate_password_hash("correct-horse"))
        self.users.create("tester_b", generate_password_hash("correct-horse"))
        self.client_a = self.logged_in_client("tester_a")
        self.client_b = self.logged_in_client("tester_b")

    def logged_in_client(self, username, password="correct-horse"):
        client = self.app.test_client()
        token = client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        return client

    @staticmethod
    def csrf(client):
        return client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]

    def create(self, client, body=None):
        payload = VALID_VEHICLE if body is None else body
        return client.post("/api/vehicles", json=payload, headers={"X-CSRF-Token": self.csrf(client)})

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status)
        body = response.get_json()
        self.assertEqual(body["error"]["code"], code)
        self.assertIsInstance(body["error"]["fields"], dict)
        self.assertEqual(body["meta"]["contract_version"], "1.0")
        return body

    def test_protected_routes_without_login_are_401(self):
        anonymous = self.app.test_client()
        self.assert_error(anonymous.get("/api/vehicles"), 401, "AUTH_REQUIRED")
        self.assert_error(anonymous.get("/api/vehicles/1"), 401, "AUTH_REQUIRED")
        # 미로그인이면 CSRF 토큰이 없어도 401이 먼저 나옵니다.
        self.assert_error(anonymous.post("/api/vehicles", json=VALID_VEHICLE), 401, "AUTH_REQUIRED")
        self.assert_error(
            anonymous.post("/api/vehicles", json=VALID_VEHICLE, headers={"X-CSRF-Token": self.csrf(anonymous)}),
            401,
            "AUTH_REQUIRED",
        )
        self.assertEqual(self.vehicles.rows, [])

    def test_post_without_csrf_is_403_and_creates_nothing(self):
        response = self.client_a.post("/api/vehicles", json=VALID_VEHICLE)
        self.assert_error(response, 403, "CSRF_FAILED")
        self.assert_error(
            self.client_a.post("/api/vehicles", json=VALID_VEHICLE, headers={"X-CSRF-Token": "wrong"}),
            403,
            "CSRF_FAILED",
        )
        self.assertEqual(self.vehicles.rows, [])

    def test_post_creates_vehicle_and_responds_with_db_values_201(self):
        response = self.create(self.client_a)
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["meta"]["contract_version"], "1.0")
        self.assertEqual(set(body["data"]), VEHICLE_FIELD_KEYS)
        self.assertEqual(body["data"], {"id": 1, **VALID_VEHICLE})
        self.assertNotIn("owner_id", body["data"])

    def test_response_never_exposes_owner_id(self):
        self.create(self.client_a)
        for response in [self.client_a.get("/api/vehicles"), self.client_a.get("/api/vehicles/1")]:
            self.assertNotIn("owner_id", response.get_data(as_text=True))

    def test_null_and_zero_are_kept_distinct(self):
        self.create(self.client_a, {"manufacturer": "기아", "mileage": 0, "reference_date": None})
        data = self.client_a.get("/api/vehicles/1").get_json()["data"]
        self.assertEqual(data["mileage"], 0)
        self.assertIsNone(data["reference_date"])

        self.vehicles.rows.clear()
        self.vehicles.next_id = 1
        self.create(self.client_a, {"manufacturer": "기아"})
        data = self.client_a.get("/api/vehicles/1").get_json()["data"]
        self.assertIsNone(data["mileage"])
        self.assertIsNone(data["reference_date"])
        self.assertEqual(data["conditions"], "unknown")

    def test_second_vehicle_for_same_account_is_409(self):
        self.assertEqual(self.create(self.client_a).status_code, 201)
        self.assert_error(self.create(self.client_a, {"manufacturer": "기아"}), 409, "CONFLICT")
        listing = self.client_a.get("/api/vehicles").get_json()["data"]
        self.assertEqual(len(listing), 1)

    def test_duplicate_from_db_race_is_409_and_rolled_back(self):
        with mock.patch("chageun.api.vehicles.find_vehicle_by_owner", return_value=None), mock.patch(
            "chageun.api.vehicles.create_vehicle",
            side_effect=pymysql.err.IntegrityError(1062, "Duplicate entry for key 'uq_vehicles_owner'"),
        ):
            response = self.create(self.client_a)
        self.assert_error(response, 409, "CONFLICT")
        self.db.rollback.assert_called()

    def test_list_returns_own_vehicle_or_empty_list(self):
        self.assertEqual(self.client_a.get("/api/vehicles").get_json()["data"], [])
        self.create(self.client_a)
        listing = self.client_a.get("/api/vehicles")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.get_json()["data"], [{"id": 1, **VALID_VEHICLE}])
        self.assertEqual(listing.get_json()["meta"]["contract_version"], "1.0")

    def test_get_own_vehicle_is_200(self):
        self.create(self.client_a)
        response = self.client_a.get("/api/vehicles/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], {"id": 1, **VALID_VEHICLE})

    def test_other_accounts_vehicle_is_404_same_as_missing(self):
        self.create(self.client_a)
        other_account = self.client_b.get("/api/vehicles/1")
        missing = self.client_b.get("/api/vehicles/999")
        self.assert_error(other_account, 404, "NOT_FOUND")
        self.assert_error(missing, 404, "NOT_FOUND")
        self.assertEqual(other_account.get_json()["error"]["message"], missing.get_json()["error"]["message"])
        self.assertEqual(self.client_b.get("/api/vehicles").get_json()["data"], [])

    def test_validation_rejects_bad_input_and_stores_nothing(self):
        cases = [
            [],
            {"owner_id": 2},
            {"generation": "XX"},
            {"generation": ["JF"]},
            {"year": 1899},
            {"year": 2036},
            {"year": True},
            {"year": "2017"},
            {"mileage": -1},
            {"mileage": 1000001},
            {"mileage": "0"},
            {"mileage": 1.5},
            {"mileage": False},
            {"reference_date": "2026/10/01"},
            {"reference_date": "20261001"},
            {"reference_date": "2026-13-01"},
            {"reference_date": "2026-02-30"},
            {"reference_date": 20261001},
            {"conditions": "broken"},
            {"conditions": None},
            {"manufacturer": ""},
            {"manufacturer": "   "},
            {"manufacturer": "가" * 41},
            {"engine": 1600},
            {"fuel": "x" * 31},
        ]
        for body in cases:
            with self.subTest(body=body):
                response = self.create(self.client_a, body)
                if isinstance(body, list):
                    self.assert_error(response, 400, "VALIDATION_ERROR")
                else:
                    error = self.assert_error(response, 400, "VALIDATION_ERROR")
                    self.assertTrue(error["error"]["fields"])
        self.assertEqual(self.vehicles.rows, [])

    def test_boundary_values_are_accepted(self):
        body = {
            "generation": "DL3",
            "year": 1900,
            "mileage": 1000000,
            "reference_date": "2024-02-29",
            "conditions": "severe",
        }
        self.assertEqual(self.create(self.client_a, body).status_code, 201)
        data = self.client_a.get("/api/vehicles/1").get_json()["data"]
        self.assertEqual(data["year"], 1900)
        self.assertEqual(data["mileage"], 1000000)
        self.assertEqual(data["reference_date"], "2024-02-29")
        self.assertEqual(data["conditions"], "severe")

    def test_database_error_is_500_and_hides_details(self):
        with mock.patch(
            "chageun.api.vehicles.create_vehicle",
            side_effect=pymysql.err.OperationalError(2013, "Lost connection password=super-secret-value"),
        ):
            response = self.create(self.client_a)
        self.assert_error(response, 500, "INTERNAL_ERROR")
        text = response.get_data(as_text=True)
        self.assertNotIn("super-secret-value", text)
        self.assertNotIn("MySQL", text)
        self.db.rollback.assert_called()


@unittest.skipUnless(
    os.environ.get("CHAGEUN_TEST_MYSQL_DATABASE"),
    "시험 MySQL 환경변수(CHAGEUN_TEST_MYSQL_DATABASE 등)가 없어 실제 DB 시험을 건너뜁니다.",
)
class MySqlVehiclePersistenceTest(unittest.TestCase):
    """실제 MySQL 시험 DB에서 차량 저장 → 재로그인 → 재조회가 유지되는지 확인합니다.

    CHAGEUN_TEST_MYSQL_* 환경변수로 시험 DB를 지정합니다. 이름에 'test'가 없는 DB는 거부합니다.
    """

    def setUp(self):
        database = os.environ["CHAGEUN_TEST_MYSQL_DATABASE"]
        if "test" not in database.lower():
            self.skipTest("시험 DB 이름에 'test'가 없어 실행하지 않습니다.")
        self.config = {
            "MYSQL_HOST": os.environ.get("CHAGEUN_TEST_MYSQL_HOST", "127.0.0.1"),
            "MYSQL_PORT": int(os.environ.get("CHAGEUN_TEST_MYSQL_PORT", "3306")),
            "MYSQL_USER": os.environ.get("CHAGEUN_TEST_MYSQL_USER", ""),
            "MYSQL_PASSWORD": os.environ.get("CHAGEUN_TEST_MYSQL_PASSWORD", ""),
            "MYSQL_DATABASE": database,
        }
        self.app = create_app(
            {"TESTING": True, "CHAGEUN_SERVER_MODE": True, "SECRET_KEY": TEST_SECRET, **self.config}
        )
        self.username = f"tester_{secrets.token_hex(4)}"
        self.password = "correct-horse-battery"

    def tearDown(self):
        if "test" not in self.config["MYSQL_DATABASE"].lower():
            return
        conn = pymysql.connect(
            host=self.config["MYSQL_HOST"],
            port=self.config["MYSQL_PORT"],
            user=self.config["MYSQL_USER"],
            password=self.config["MYSQL_PASSWORD"],
            database=self.config["MYSQL_DATABASE"],
            charset="utf8mb4",
        )
        try:
            with conn.cursor() as cursor:
                # vehicles는 users 삭제 시 CASCADE로 함께 지워집니다.
                cursor.execute("DELETE FROM users WHERE username = %s", (self.username,))
            conn.commit()
        finally:
            conn.close()

    def login(self, client):
        token = client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        response = client.post(
            "/api/auth/login",
            json={"username": self.username, "password": self.password},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_vehicle_saved_then_reread_after_relogin(self):
        client = self.app.test_client()
        token = client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        register = client.post(
            "/api/auth/register",
            json={"username": self.username, "password": self.password},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(register.status_code, 201)

        first = self.login(self.app.test_client())
        token = first.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
        created = first.post("/api/vehicles", json=VALID_VEHICLE, headers={"X-CSRF-Token": token})
        self.assertEqual(created.status_code, 201)
        vehicle_id = created.get_json()["data"]["id"]

        # 새 클라이언트로 다시 로그인해 DB에서 읽은 값을 확인합니다.
        second = self.login(self.app.test_client())
        listing = second.get("/api/vehicles").get_json()["data"]
        self.assertEqual(listing, [{"id": vehicle_id, **VALID_VEHICLE}])
        self.assertEqual(second.get(f"/api/vehicles/{vehicle_id}").get_json()["data"]["mileage"], 0)


if __name__ == "__main__":
    unittest.main()
