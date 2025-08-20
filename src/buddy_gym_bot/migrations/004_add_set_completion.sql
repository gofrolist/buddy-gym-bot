-- Migration: Add set completion tracking
-- Add is_completed column to track whether sets are completed

-- Add is_completed column with default value true
ALTER TABLE set_rows ADD COLUMN IF NOT EXISTS is_completed BOOLEAN DEFAULT TRUE;

-- Update existing rows to mark all existing sets as completed
UPDATE set_rows SET is_completed = TRUE WHERE is_completed IS NULL;

-- Make the column NOT NULL after populating existing data
ALTER TABLE set_rows ALTER COLUMN is_completed SET NOT NULL;

-- Add index for better query performance
CREATE INDEX IF NOT EXISTS idx_set_rows_is_completed ON set_rows(is_completed);
