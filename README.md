# Second Brain AI

AI Personal Knowledge Engine with PDF, image OCR, and YouTube ingestion.

## Repo Structure

- `backend/` FastAPI backend, RAG, persistence, analytics, study tools
- `Frontend/` React dashboard UI

## Local Run

Backend:

```powershell
cd backend
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd Frontend
npm install
npm run dev
```

## Deployment

- Frontend: Vercel
- Backend: Render or Railway
