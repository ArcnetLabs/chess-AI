SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN ('tier', 'ai_analyses_used', 'ai_analyses_limit', 'trial_exhausted_at', 'total_games', 'analyzed_games')
ORDER BY column_name;
