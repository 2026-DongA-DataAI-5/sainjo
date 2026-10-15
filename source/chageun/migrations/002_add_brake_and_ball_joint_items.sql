-- Extend the supported record item list (apply after migration 001).
ALTER TABLE records
    DROP CONSTRAINT ck_records_item;

ALTER TABLE records
    ADD CONSTRAINT ck_records_item
    CHECK (item_key IN ('engine-oil', 'spark-plugs', 'drive-belt', 'brake-pads-discs', 'lower-arm-ball-joint'));
