"""Verify the ordered MySQL migration chain against an isolated disposable DB."""

import os
from pathlib import Path

import pymysql


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DATABASE = "chageun_migration_test"
EXPECTED_CONFIRMATION = "disposable-migration-db"
MIGRATIONS = (
    "001_vehicle_date_and_service_items.sql",
    "002_add_brake_and_ball_joint_items.sql",
    "003_add_record_component_position.sql",
)


def split_sql(path):
    text = "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("--")
    )
    return [statement.strip() for statement in text.split(";") if statement.strip()]


def main():
    database = os.environ.get("CHAGEUN_MIGRATION_TEST_DATABASE")
    confirmation = os.environ.get("CHAGEUN_MIGRATION_TEST_CONFIRM")
    if database != EXPECTED_DATABASE or confirmation != EXPECTED_CONFIRMATION:
        raise SystemExit(
            "Refusing to run: set the exact dedicated CI database and confirmation values."
        )

    host = os.environ.get("CHAGEUN_MIGRATION_TEST_HOST")
    user = os.environ.get("CHAGEUN_MIGRATION_TEST_USER")
    password = os.environ.get("CHAGEUN_MIGRATION_TEST_PASSWORD")
    if not host or not user or password is None:
        raise SystemExit("Refusing to run: migration-test connection settings are incomplete.")

    connection = pymysql.connect(
        host=host,
        port=int(os.environ.get("CHAGEUN_MIGRATION_TEST_PORT", "3306")),
        user=user,
        password=password,
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS chageun_migration_test CHARACTER SET utf8mb4")
            cursor.execute("USE chageun_migration_test")
            cursor.execute("SELECT DATABASE()")
            if cursor.fetchone()[0] != EXPECTED_DATABASE:
                raise RuntimeError("Connected to an unexpected migration-test database.")
            cursor.execute("SHOW TABLES")
            if cursor.fetchall():
                raise RuntimeError("Migration-test database is not empty; refusing to modify it.")

            for statement in split_sql(ROOT / "source/tests/fixtures/legacy_mysql_schema.sql"):
                cursor.execute(statement)

            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                ("migration-check", "not-a-real-login-hash"),
            )
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO vehicles (owner_id, manufacturer, model, mileage) VALUES (%s, %s, %s, %s)",
                (user_id, "기아", "K5", 90000),
            )
            vehicle_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO records (vehicle_id, kind, item_key, work_type, mileage, result) "
                "VALUES (%s, 'previous_history', 'engine-oil', 'replacement', 85000, 'legacy record')",
                (vehicle_id,),
            )

            migration_dir = ROOT / "source/chageun/migrations"
            for migration in MIGRATIONS:
                for statement in split_sql(migration_dir / migration):
                    cursor.execute(statement)

            cursor.execute("SELECT in_service_date FROM vehicles WHERE id = %s", (vehicle_id,))
            if cursor.fetchone()[0] is not None:
                raise AssertionError("Legacy vehicle was not preserved with unknown service date.")
            cursor.execute(
                "SELECT item_key, mileage, result, component_position FROM records WHERE vehicle_id = %s",
                (vehicle_id,),
            )
            legacy_record = cursor.fetchone()
            if legacy_record != ("engine-oil", 85000, "legacy record", "unknown"):
                raise AssertionError(f"Legacy service record changed during migration: {legacy_record!r}")

            items_and_positions = (
                ("spark-plugs", "unknown"),
                ("drive-belt", "unknown"),
                ("brake-pads-discs", "front_left"),
                ("lower-arm-ball-joint", "front_right"),
            )
            for item_key, position in items_and_positions:
                cursor.execute(
                    "INSERT INTO records (vehicle_id, kind, item_key, component_position, work_type) "
                    "VALUES (%s, 'maintenance_result', %s, %s, 'inspection')",
                    (vehicle_id, item_key, position),
                )

            try:
                cursor.execute(
                    "INSERT INTO records (vehicle_id, kind, item_key, component_position, work_type) "
                    "VALUES (%s, 'maintenance_result', 'brake-pads-discs', 'center', 'inspection')",
                    (vehicle_id,),
                )
            except pymysql.err.MySQLError as error:
                if not error.args or error.args[0] != 3819:
                    raise
            else:
                raise AssertionError("Database accepted invalid component position 'center'.")

            cursor.execute("SELECT COUNT(*) FROM records WHERE vehicle_id = %s", (vehicle_id,))
            if cursor.fetchone()[0] != 5:
                raise AssertionError("Expected one preserved record and four supported new records.")

        connection.commit()
        print("Migration chain 001 → 002 → 003 preserves legacy data and enforces current constraints.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
