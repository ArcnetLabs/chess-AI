-- Reset user stats for fresh testing
UPDATE users 
SET 
  total_games = 0,
  analyzed_games = 0,
  ai_analyses_used = 0
WHERE id = 1;

-- Delete all games and analyses for user 1
DELETE FROM game_analyses WHERE game_id IN (SELECT id FROM games WHERE user_id = 1);
DELETE FROM games WHERE user_id = 1;

-- Verify
SELECT id, chesscom_username, total_games, analyzed_games, ai_analyses_used, ai_analyses_limit
FROM users WHERE id = 1;
