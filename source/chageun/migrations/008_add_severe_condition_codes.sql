-- Store the selected Kia manual severe-use condition numbers without changing legacy rows.
ALTER TABLE vehicles
    ADD COLUMN severe_condition_codes VARCHAR(48) NOT NULL DEFAULT '[]' AFTER conditions;
