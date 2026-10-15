"""정비소 방문 전에 선택한 질문 키. 정비 결과와는 별도 자료입니다."""

from .db import get_db

MAX_SELECTIONS = 200


def list_keys(vehicle_id):
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT question_key FROM question_selections WHERE vehicle_id = %s ORDER BY question_key",
            (vehicle_id,),
        )
        return [row["question_key"] for row in cursor.fetchall()]


def clear(vehicle_id):
    with get_db().cursor() as cursor:
        cursor.execute("DELETE FROM question_selections WHERE vehicle_id = %s", (vehicle_id,))


def set_selected(vehicle_id, question_key, selected):
    with get_db().cursor() as cursor:
        # 서로 다른 탭의 선택도 한 차량의 제한을 넘거나 서로 덮어쓰지 않습니다.
        cursor.execute("SELECT id FROM vehicles WHERE id = %s FOR UPDATE", (vehicle_id,))
        if selected:
            cursor.execute("SELECT question_key FROM question_selections WHERE vehicle_id = %s FOR UPDATE", (vehicle_id,))
            keys = [row["question_key"] for row in cursor.fetchall()]
            if question_key not in keys and len(keys) >= MAX_SELECTIONS:
                return False
            cursor.execute(
                "INSERT IGNORE INTO question_selections (vehicle_id, question_key) VALUES (%s, %s)",
                (vehicle_id, question_key),
            )
        else:
            cursor.execute(
                "DELETE FROM question_selections WHERE vehicle_id = %s AND question_key = %s",
                (vehicle_id, question_key),
            )
        return True
