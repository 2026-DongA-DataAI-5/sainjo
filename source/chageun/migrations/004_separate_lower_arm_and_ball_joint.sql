-- Add separate record keys for the lower arm and ball joint.
-- Keep the combined historical key so earlier user-entered rows are preserved.
ALTER TABLE records
    DROP CONSTRAINT ck_records_item;

ALTER TABLE records
    ADD CONSTRAINT ck_records_item
    CHECK (item_key IN ('engine-oil', 'spark-plugs', 'drive-belt', 'brake-pads-discs', 'ball-joint', 'lower-arm', 'lower-arm-ball-joint'));
