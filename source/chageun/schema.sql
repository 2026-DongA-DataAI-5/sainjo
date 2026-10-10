-- 차근 MySQL 스키마 v1.0 (1단계: users / vehicles / records)
--
-- 주의: 시험 DB 전용입니다. 실제 사용자 DB에 실행하거나 테스트 중 DROP하지 마세요.
-- 적용 예시(시험 DB 이름을 직접 지정):
--   mysql -u <user> -p <chageun_test_db> < chageun/schema.sql
--
-- 삭제 정책: 사용자 삭제 시 차량, 차량 삭제 시 기록을 함께 삭제(CASCADE)합니다.
-- 계정당 차량 1대는 vehicles.owner_id UNIQUE로 보장합니다.
-- 날짜·거리가 없는 값은 NULL입니다. 0km와 NULL은 다른 값입니다.
-- 자료 확인일(checked_date)은 증빙 자동 검증 결과가 아닙니다.

CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(30) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS vehicles (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    owner_id INT UNSIGNED NOT NULL,
    manufacturer VARCHAR(40) NULL,
    model VARCHAR(40) NULL,
    generation VARCHAR(10) NULL,
    year SMALLINT NULL,
    engine VARCHAR(60) NULL,
    fuel VARCHAR(30) NULL,
    transmission VARCHAR(40) NULL,
    mileage INT UNSIGNED NULL,
    reference_date DATE NULL,
    conditions VARCHAR(10) NOT NULL DEFAULT 'unknown',
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_vehicles_owner (owner_id),
    CONSTRAINT fk_vehicles_owner FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT ck_vehicles_generation CHECK (generation IS NULL OR generation IN ('DL3', 'JF')),
    CONSTRAINT ck_vehicles_conditions CHECK (conditions IN ('normal', 'severe', 'unknown')),
    CONSTRAINT ck_vehicles_year CHECK (year IS NULL OR year BETWEEN 1900 AND 2035),
    CONSTRAINT ck_vehicles_mileage CHECK (mileage IS NULL OR mileage <= 1000000)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

CREATE TABLE IF NOT EXISTS records (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    vehicle_id INT UNSIGNED NOT NULL,
    kind VARCHAR(30) NOT NULL,
    item_key VARCHAR(40) NOT NULL,
    work_type VARCHAR(20) NOT NULL,
    record_date DATE NULL,
    mileage INT UNSIGNED NULL,
    result VARCHAR(2000) NULL,
    source VARCHAR(100) NULL,
    checked_date DATE NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY idx_records_vehicle_order (vehicle_id, record_date, created_at, id),
    CONSTRAINT fk_records_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicles (id) ON DELETE CASCADE,
    CONSTRAINT ck_records_kind CHECK (kind IN ('previous_history', 'maintenance_result')),
    CONSTRAINT ck_records_item CHECK (item_key = 'engine-oil'),
    CONSTRAINT ck_records_work_type CHECK (work_type IN ('inspection', 'replacement', 'unknown')),
    CONSTRAINT ck_records_mileage CHECK (mileage IS NULL OR mileage <= 1000000)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;
