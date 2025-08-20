-- Migration: Add dual-unit storage for weights
-- This allows storing both kg and lbs values to prevent conversion errors

-- Add new columns for dual-unit storage
ALTER TABLE set_rows ADD COLUMN IF NOT EXISTS weight_lbs DECIMAL(6,2);
ALTER TABLE set_rows ADD COLUMN IF NOT EXISTS input_unit VARCHAR(3) DEFAULT 'kg';

-- Update existing rows to populate weight_lbs based on current weight_kg
-- This ensures backward compatibility
UPDATE set_rows
SET weight_lbs = ROUND(weight_kg * 2.20462, 0),
    input_unit = 'kg'
WHERE weight_lbs IS NULL;

-- Make weight_lbs NOT NULL after populating existing data
ALTER TABLE set_rows ALTER COLUMN weight_lbs SET NOT NULL;

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_set_rows_weight_lbs ON set_rows(weight_lbs);
CREATE INDEX IF NOT EXISTS idx_set_rows_input_unit ON set_rows(input_unit);
