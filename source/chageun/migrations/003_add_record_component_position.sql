-- Add explicit axle/side to each service record (apply after migrations 001 and 002).
-- Existing records remain intact and are marked as position unknown.
ALTER TABLE records
    ADD COLUMN component_position VARCHAR(20) NOT NULL DEFAULT 'unknown' AFTER item_key;

ALTER TABLE records
    ADD CONSTRAINT ck_records_component_position
    CHECK (component_position IN ('unknown', 'front', 'rear', 'left', 'right', 'front_left', 'front_right', 'rear_left', 'rear_right'));
