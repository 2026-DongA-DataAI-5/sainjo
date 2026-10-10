"""vehicles 테이블 접근. 커밋은 호출하는 API가 합니다. 모든 SQL은 파라미터 바인딩을 사용합니다.

계정당 차량 1대는 DB의 UNIQUE(owner_id)가 최종적으로 보장합니다.
"""

from .db import get_db


def create_vehicle(owner_id, values):
    with get_db().cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO vehicles
                (owner_id, manufacturer, model, generation, year, engine,
                 fuel, transmission, mileage, reference_date, conditions)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                values["manufacturer"],
                values["model"],
                values["generation"],
                values["year"],
                values["engine"],
                values["fuel"],
                values["transmission"],
                values["mileage"],
                values["reference_date"],
                values["conditions"],
            ),
        )
        return cursor.lastrowid


def find_vehicle_by_owner(owner_id):
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT id, manufacturer, model, generation, year, engine, fuel, transmission, "
            "mileage, reference_date, conditions FROM vehicles WHERE owner_id = %s",
            (owner_id,),
        )
        return cursor.fetchone()


def find_vehicle_by_id_and_owner(vehicle_id, owner_id):
    # 소유자 조건을 함께 걸어, 다른 계정의 차량은 존재 여부와 상관없이 조회되지 않습니다.
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT id, manufacturer, model, generation, year, engine, fuel, transmission, "
            "mileage, reference_date, conditions FROM vehicles WHERE id = %s AND owner_id = %s",
            (vehicle_id, owner_id),
        )
        return cursor.fetchone()
