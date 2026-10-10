"""users 테이블 접근. 커밋은 호출하는 API가 합니다. 모든 SQL은 파라미터 바인딩을 사용합니다."""

from .db import get_db


def create_user(username, password_hash):
    with get_db().cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, password_hash),
        )
        return cursor.lastrowid


def find_user_by_username(username):
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE username = %s",
            (username,),
        )
        return cursor.fetchone()


def find_user_by_id(user_id):
    with get_db().cursor() as cursor:
        cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
