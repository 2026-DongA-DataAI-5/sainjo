"""엔진오일 기록 저장소. 소유권은 호출 API에서 확인하며 커밋도 API가 담당합니다."""

from .db import get_db

RECORD_COLUMNS = "id, vehicle_id, kind, item_key, work_type, record_date, mileage, result, source, checked_date, created_at"
RECORD_ORDER = "record_date DESC, created_at DESC, id DESC"


def create_record(vehicle_id, values):
    with get_db().cursor() as cursor:
        cursor.execute(
            "INSERT INTO records (vehicle_id, kind, item_key, work_type, record_date, mileage, result, source, checked_date) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (vehicle_id, values["kind"], values["item_key"], values["work_type"], values["record_date"],
             values["mileage"], values["result"], values["source"], values["checked_date"]),
        )
        return cursor.lastrowid


def find_record_by_id_and_vehicle(record_id, vehicle_id):
    with get_db().cursor() as cursor:
        cursor.execute(f"SELECT {RECORD_COLUMNS} FROM records WHERE id = %s AND vehicle_id = %s", (record_id, vehicle_id))
        return cursor.fetchone()


def find_record_by_id_and_owner(record_id, owner_id):
    columns = ", ".join(f"r.{column.strip()}" for column in RECORD_COLUMNS.split(","))
    with get_db().cursor() as cursor:
        cursor.execute(
            f"SELECT {columns} FROM records r JOIN vehicles v ON v.id = r.vehicle_id "
            "WHERE r.id = %s AND v.owner_id = %s",
            (record_id, owner_id),
        )
        return cursor.fetchone()


def update_record(record_id, owner_id, values):
    with get_db().cursor() as cursor:
        cursor.execute(
            "UPDATE records r JOIN vehicles v ON v.id = r.vehicle_id "
            "SET r.kind = %s, r.item_key = %s, r.work_type = %s, r.record_date = %s, "
            "r.mileage = %s, r.result = %s, r.source = %s, r.checked_date = %s "
            "WHERE r.id = %s AND v.owner_id = %s",
            (values["kind"], values["item_key"], values["work_type"], values["record_date"],
             values["mileage"], values["result"], values["source"], values["checked_date"],
             record_id, owner_id),
        )
        return cursor.rowcount


def delete_record(record_id, owner_id):
    with get_db().cursor() as cursor:
        cursor.execute(
            "DELETE r FROM records r JOIN vehicles v ON v.id = r.vehicle_id "
            "WHERE r.id = %s AND v.owner_id = %s",
            (record_id, owner_id),
        )
        return cursor.rowcount


def list_records_by_vehicle(vehicle_id, page, page_size):
    with get_db().cursor() as cursor:
        cursor.execute(
            f"SELECT {RECORD_COLUMNS} FROM records WHERE vehicle_id = %s ORDER BY {RECORD_ORDER} LIMIT %s OFFSET %s",
            (vehicle_id, page_size, (page - 1) * page_size),
        )
        return cursor.fetchall()


def count_records(vehicle_id):
    with get_db().cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM records WHERE vehicle_id = %s", (vehicle_id,))
        return cursor.fetchone()["total"]


def list_records_for_management(vehicle_id):
    # 판단에서 오래된 기록도 필요하므로 화면의 페이지 크기로 잘라 전달하지 않습니다.
    with get_db().cursor() as cursor:
        cursor.execute(f"SELECT {RECORD_COLUMNS} FROM records WHERE vehicle_id = %s ORDER BY {RECORD_ORDER}", (vehicle_id,))
        return cursor.fetchall()
