-- Migration: Single unit storage with input tracking
-- Store weights in kg (canonical) and track user input for auditability

-- Add new columns for input tracking
ALTER TABLE set_rows ADD COLUMN IF NOT EXISTS input_weight DECIMAL(7,3);
ALTER TABLE set_rows ADD COLUMN IF NOT EXISTS input_unit VARCHAR(3) DEFAULT 'kg';

-- Update existing rows to populate input tracking
-- For existing data, assume input was in kg
UPDATE set_rows
SET input_weight = weight_kg,
    input_unit = 'kg'
WHERE input_weight IS NULL;

-- Make input_weight NOT NULL after populating existing data
ALTER TABLE set_rows ALTER COLUMN input_weight SET NOT NULL;

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_set_rows_input_weight ON set_rows(input_weight);
CREATE INDEX IF NOT EXISTS idx_set_rows_input_unit ON set_rows(input_unit);
