"""차근 API v1.0 - 1단계: 최소 인증(가입·로그인·로그아웃·내 정보).

규약: docs 'API 주소·인증·오류·목록' 절. 응답 data는 snake_case, 비밀번호·해시·내부 DB 값은 응답하지 않습니다.
"""

import re
import secrets
from datetime import date
from functools import wraps

import pymysql
from flask import Blueprint, current_app, g, jsonify, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from .repositories import users, vehicles
from .repositories.db import get_db

api = Blueprint("api", __name__, url_prefix="/api")

CONTRACT_VERSION = "1.0"
USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,30}")
PASSWORD_MIN = 8
PASSWORD_MAX = 128
AUTH_FIELDS = {"username", "password"}
DUPLICATE_KEY_ERROR = 1062

# 차량 입력 규칙은 schema.sql의 vehicles 제약과 맞춥니다.
VEHICLE_TEXT_LIMITS = {"manufacturer": 40, "model": 40, "engine": 60, "fuel": 30, "transmission": 40}
VEHICLE_GENERATIONS = {"DL3", "JF"}
VEHICLE_CONDITIONS = {"normal", "severe", "unknown"}
VEHICLE_FIELDS = set(VEHICLE_TEXT_LIMITS) | {"generation", "year", "mileage", "reference_date", "conditions"}
VEHICLE_YEAR_MIN = 1900
VEHICLE_YEAR_MAX = 2035
VEHICLE_MILEAGE_MAX = 1000000
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")

# 로그인 실패 시 아이디 존재 여부가 시간 차이로 드러나지 않도록 항상 해시 검사를 한 번 수행합니다.
DUMMY_HASH = generate_password_hash("chageun-dummy-password")

HTTP_ERROR_CODES = {
    400: "VALIDATION_ERROR",
    401: "AUTH_REQUIRED",
    403: "CSRF_FAILED",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "VALIDATION_ERROR",
}


def ok(data, status=200):
    body = {
        "data": data,
        "meta": {"contract_version": CONTRACT_VERSION, "mode": "live", "calculation_mode": "none"},
    }
    return jsonify(body), status


def fail(code, message, status, fields=None):
    body = {
        "error": {"code": code, "message": message, "fields": fields or {}},
        "meta": {"contract_version": CONTRACT_VERSION},
    }
    return jsonify(body), status


def _csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_protected(view):
    """POST/PATCH/DELETE 전 X-CSRF-Token 헤더를 검사합니다. 누락·불일치는 403입니다."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = session.get("csrf_token")
        sent = request.headers.get("X-CSRF-Token", "")
        if not expected or not sent or not secrets.compare_digest(
            expected.encode("utf-8"), sent.encode("utf-8")
        ):
            return fail("CSRF_FAILED", "요청을 확인할 수 없습니다. 화면을 새로고침한 뒤 다시 시도해 주세요.", 403)
        return view(*args, **kwargs)

    return wrapped


def login_required(view):
    """보호 API는 미로그인 401을 가장 먼저 반환합니다. 다른 계정의 자원은 이후 단계에서 404로 막습니다."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return fail("AUTH_REQUIRED", "로그인이 필요합니다.", 401)
        return view(*args, **kwargs)

    return wrapped


def _json_body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else None


def _credential_fields(body, register):
    fields = {}
    for key in set(body) - AUTH_FIELDS:
        fields[key] = "허용되지 않은 필드입니다."

    username = body.get("username")
    password = body.get("password")

    if register:
        if not isinstance(username, str) or not USERNAME_PATTERN.fullmatch(username):
            fields["username"] = "영문 소문자·숫자·밑줄을 사용해 3~30자로 입력해 주세요."
        if not isinstance(password, str) or not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
            fields["password"] = "비밀번호는 8~128자로 입력해 주세요."
    else:
        if not isinstance(username, str) or not 1 <= len(username) <= 30:
            fields["username"] = "아이디를 입력해 주세요."
        if not isinstance(password, str) or not 1 <= len(password) <= PASSWORD_MAX:
            fields["password"] = "비밀번호를 입력해 주세요."
    return fields


@api.get("/auth/csrf")
def csrf():
    return ok({"csrf_token": _csrf_token()})


@api.post("/auth/register")
@csrf_protected
def register():
    body = _json_body()
    if body is None:
        return fail("VALIDATION_ERROR", "입력을 확인해 주세요", 400, {})
    fields = _credential_fields(body, register=True)
    if fields:
        return fail("VALIDATION_ERROR", "입력을 확인해 주세요", 400, fields)

    username = body["username"]
    db = get_db()
    try:
        user_id = users.create_user(username, generate_password_hash(body["password"]))
        db.commit()
    except pymysql.err.IntegrityError as error:
        db.rollback()
        if error.args and error.args[0] == DUPLICATE_KEY_ERROR:
            return fail("CONFLICT", "이미 사용 중인 아이디입니다.", 409, {"username": "이미 사용 중인 아이디입니다."})
        raise
    except Exception:
        db.rollback()
        raise

    # 가입 후 자동 로그인하지 않습니다.
    return ok({"id": user_id, "username": username}, 201)


@api.post("/auth/login")
@csrf_protected
def login():
    body = _json_body()
    if body is None:
        return fail("VALIDATION_ERROR", "입력을 확인해 주세요", 400, {})
    fields = _credential_fields(body, register=False)
    if fields:
        return fail("VALIDATION_ERROR", "입력을 확인해 주세요", 400, fields)

    user = users.find_user_by_username(body["username"])
    password_ok = check_password_hash(user["password_hash"] if user else DUMMY_HASH, body["password"])
    if user is None or not password_ok:
        return fail("INVALID_CREDENTIALS", "아이디 또는 비밀번호가 올바르지 않습니다.", 401)

    # 로그인 성공 시 세션을 새로 만들고 CSRF 토큰도 다시 발급합니다. 클라이언트는 /api/auth/csrf로 새 토큰을 받습니다.
    session.clear()
    session["user_id"] = user["id"]
    _csrf_token()
    return ok({"id": user["id"], "username": user["username"]})


@api.post("/auth/logout")
@login_required
@csrf_protected
def logout():
    session.clear()
    return ok({"logged_out": True})


@api.get("/auth/me")
@login_required
def me():
    user = users.find_user_by_id(session["user_id"])
    if user is None:
        session.clear()
        return fail("AUTH_REQUIRED", "로그인이 필요합니다.", 401)
    return ok({"id": user["id"], "username": user["username"]})


def _is_int(value):
    # bool은 int의 하위 타입이므로 따로 걸러냅니다.
    return isinstance(value, int) and not isinstance(value, bool)


def _vehicle_values(body):
    """차량 입력을 검증해 DB에 넣을 값을 돌려줍니다. 미입력(키 없음)과 null은 '값 없음'으로 같게 저장하되,
    주행거리 0과 null, 날짜 값과 null은 서로 다른 값으로 보존합니다."""
    fields = {}
    for key in set(body) - VEHICLE_FIELDS:
        fields[key] = "허용되지 않은 필드입니다."

    values = {}

    for key, limit in VEHICLE_TEXT_LIMITS.items():
        value = body.get(key)
        if value is None:
            values[key] = None
        elif isinstance(value, str) and 1 <= len(value.strip()) <= limit:
            values[key] = value.strip()
        else:
            fields[key] = f"1~{limit}자로 입력하거나 비워 두세요."

    generation = body.get("generation")
    if generation is None or (isinstance(generation, str) and generation in VEHICLE_GENERATIONS):
        values["generation"] = generation
    else:
        fields["generation"] = "DL3 또는 JF 중에서 선택해 주세요."

    year = body.get("year")
    if year is None or (_is_int(year) and VEHICLE_YEAR_MIN <= year <= VEHICLE_YEAR_MAX):
        values["year"] = year
    else:
        fields["year"] = f"{VEHICLE_YEAR_MIN}~{VEHICLE_YEAR_MAX} 사이의 연식을 입력해 주세요."

    mileage = body.get("mileage")
    if mileage is None or (_is_int(mileage) and 0 <= mileage <= VEHICLE_MILEAGE_MAX):
        values["mileage"] = mileage
    else:
        fields["mileage"] = f"0~{VEHICLE_MILEAGE_MAX}km 사이로 입력해 주세요. 모르면 비워 두세요."

    reference_date = body.get("reference_date")
    if reference_date is None:
        values["reference_date"] = None
    elif isinstance(reference_date, str) and DATE_PATTERN.fullmatch(reference_date):
        try:
            date.fromisoformat(reference_date)
            values["reference_date"] = reference_date
        except ValueError:
            fields["reference_date"] = "YYYY-MM-DD 형식의 실제 날짜를 입력해 주세요."
    else:
        fields["reference_date"] = "YYYY-MM-DD 형식의 날짜를 입력하거나 비워 두세요."

    conditions = body.get("conditions", "unknown")
    if isinstance(conditions, str) and conditions in VEHICLE_CONDITIONS:
        values["conditions"] = conditions
    else:
        fields["conditions"] = "normal, severe, unknown 중에서 선택해 주세요."

    return values, fields


def _vehicle_out(row):
    reference_date = row["reference_date"]
    return {
        "id": row["id"],
        "manufacturer": row["manufacturer"],
        "model": row["model"],
        "generation": row["generation"],
        "year": row["year"],
        "engine": row["engine"],
        "fuel": row["fuel"],
        "transmission": row["transmission"],
        "mileage": row["mileage"],
        "reference_date": reference_date.isoformat() if reference_date is not None else None,
        "conditions": row["conditions"],
    }


def _vehicle_conflict():
    return fail("CONFLICT", "이미 등록된 차량이 있습니다. 계정당 차량은 1대만 등록할 수 있습니다.", 409)


@api.get("/vehicles")
@login_required
def list_vehicles():
    row = vehicles.find_vehicle_by_owner(session["user_id"])
    return ok([_vehicle_out(row)] if row is not None else [])


@api.post("/vehicles")
@login_required
@csrf_protected
def add_vehicle():
    body = _json_body()
    if body is None:
        return fail("VALIDATION_ERROR", "입력을 확인해 주세요", 400, {})
    values, fields = _vehicle_values(body)
    if fields:
        return fail("VALIDATION_ERROR", "입력을 확인해 주세요", 400, fields)

    owner_id = session["user_id"]
    db = get_db()
    try:
        if vehicles.find_vehicle_by_owner(owner_id) is not None:
            db.rollback()
            return _vehicle_conflict()
        vehicle_id = vehicles.create_vehicle(owner_id, values)
        db.commit()
    except pymysql.err.IntegrityError as error:
        db.rollback()
        # 동시 요청으로 두 번째 차량이 들어오면 uq_vehicles_owner가 1062를 냅니다.
        if error.args and error.args[0] == DUPLICATE_KEY_ERROR:
            return _vehicle_conflict()
        raise
    except Exception:
        db.rollback()
        raise

    # 응답은 입력값이 아니라 저장 후 DB에서 다시 읽은 값으로 만듭니다.
    row = vehicles.find_vehicle_by_id_and_owner(vehicle_id, owner_id)
    if row is None:
        raise RuntimeError("저장한 차량을 다시 읽지 못했습니다.")
    return ok(_vehicle_out(row), 201)


@api.get("/vehicles/<int:vehicle_id>")
@login_required
def get_vehicle(vehicle_id):
    # 다른 계정의 차량도 없는 차량과 똑같이 404로 응답합니다.
    row = vehicles.find_vehicle_by_id_and_owner(vehicle_id, session["user_id"])
    if row is None:
        return fail("NOT_FOUND", "차량을 찾을 수 없습니다.", 404)
    return ok(_vehicle_out(row))


@api.errorhandler(Exception)
def handle_error(error):
    if isinstance(error, HTTPException):
        code = HTTP_ERROR_CODES.get(error.code, "INTERNAL_ERROR")
        return fail(code, "요청을 처리할 수 없습니다.", error.code or 500)

    # DB·내부 오류의 세부 내용은 응답에 넣지 않고 서버 로그에만 남깁니다.
    db = g.get("db")
    if db is not None:
        try:
            db.rollback()
        except Exception:
            pass
    current_app.logger.exception("API 처리 중 내부 오류")
    return fail("INTERNAL_ERROR", "처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", 500)
