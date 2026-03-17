
backend:
python -m uvicorn app.__main__:app --reload --host 0.0.0.0 --port 8000

frontend: npm run dev

