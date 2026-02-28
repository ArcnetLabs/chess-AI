-- Migration to add missing fields to game_analyses table
-- Run this SQL in your Supabase SQL editor

ALTER TABLE game_analyses 
ADD COLUMN IF NOT EXISTS accuracy_percentage FLOAT,
ADD COLUMN IF NOT EXISTS analysis_data JSONB,
ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ;

-- Update existing records to have analyzed_at = created_at
UPDATE game_analyses 
SET analyzed_at = created_at 
WHERE analyzed_at IS NULL;

-- Verify the changes
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'game_analyses' 
ORDER BY ordinal_position;
