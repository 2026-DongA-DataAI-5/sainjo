-- Minimal schema representing the database immediately before migrations 001-003.
-- Used only by check_migrations.py against its dedicated disposable CI database.
CREATE TABLE users (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(30) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE vehicles (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE records (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
