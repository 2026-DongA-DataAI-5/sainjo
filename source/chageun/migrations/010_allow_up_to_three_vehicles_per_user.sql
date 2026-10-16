-- Remove the former one-vehicle-per-account unique index.
-- The live API now enforces a three-vehicle limit while holding the owner row lock.
ALTER TABLE vehicles
    ADD KEY idx_vehicles_owner (owner_id);

ALTER TABLE vehicles
    DROP INDEX uq_vehicles_owner;
