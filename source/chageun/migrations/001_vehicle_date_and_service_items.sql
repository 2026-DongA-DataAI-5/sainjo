-- Existing Cha-geun DB migration (apply once per database).
-- This is additive for vehicles: existing rows retain their data and receive NULL.
-- Supported record items now include engine oil, spark plugs, and drive belts.

ALTER TABLE vehicles
    ADD COLUMN in_service_date DATE NULL AFTER reference_date;

ALTER TABLE records
    DROP CONSTRAINT ck_records_item;

ALTER TABLE records
    ADD CONSTRAINT ck_records_item
    CHECK (item_key IN ('engine-oil', 'spark-plugs', 'drive-belt'));
