@echo off
echo Starting Chess Insight AI Backend (Connected to Supabase)...
echo.

cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
