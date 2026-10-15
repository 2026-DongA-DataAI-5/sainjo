-- Add the source-checked coolant record item without changing existing records.
ALTER TABLE records
    DROP CONSTRAINT ck_records_item;

ALTER TABLE records
    ADD CONSTRAINT ck_records_item
    CHECK (item_key IN ('engine-oil', 'spark-plugs', 'drive-belt', 'brake-pads-discs', 'ball-joint', 'lower-arm', 'lower-arm-ball-joint', 'brake-fluid', 'cabin-air-filter', 'coolant'));
