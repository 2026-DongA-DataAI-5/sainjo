"""차근 API v1.0 - 1단계: 최소 인증(가입·로그인·로그아웃·내 정보).

규약: docs 'API 주소·인증·오류·목록' 절. 응답 data는 snake_case, 비밀번호·해시·내부 DB 값은 응답하지 않습니다.
"""

import re
import secrets
from functools import wraps

import pymysql
from flask import Blueprint, current_app, g, jsonify, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from .repositories import users
from .repositories.db import get_db

api = Blueprint("api", __name__, url_prefix="/api")

CONTRACT_VERSION = "1.0"
USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,30}")
PASSWORD_MIN = 8
PASSWORD_MAX = 128
AUTH_FIELDS = {"username", "password"}
DUPLICATE_KEY_ERROR = 1062

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
