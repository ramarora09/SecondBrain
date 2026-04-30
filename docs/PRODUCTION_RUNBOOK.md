# Second Brain AI Production Runbook

## Core Deploy Targets

- Frontend: Vercel, root directory `Frontend`, build command `npm run build`, output `dist`.
- Backend: Render or Railway, root directory `backend`, start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.

## Required Environment

Backend:

```env
GROQ_API_KEY=
SECOND_BRAIN_API_KEY=
EMBEDDING_BACKEND=hash
PDF_MAX_PAGES=30
PDF_MAX_CHARS=100000
PDF_OCR_MAX_PAGES=8
PDF_OCR_MAX_CHARS=50000
YOUTUBE_TRANSCRIPT_LANGUAGES=en,hi,en-US,en-GB
YOUTUBE_PROXY_URL=
WEBSHARE_PROXY_USERNAME=
WEBSHARE_PROXY_PASSWORD=
```

Frontend:

```env
VITE_API_BASE_URL=https://your-backend.example.com/api
VITE_API_KEY=
```

Set `VITE_API_KEY` only when `SECOND_BRAIN_API_KEY` is configured on the backend.

## Verification Checklist

1. Open `/api/health` and confirm `status` is `ok`.
2. Upload a text PDF and ask for a summary.
3. Upload an image and confirm OCR preview appears.
4. Paste a YouTube URL and confirm the source is indexed.
5. If YouTube is blocked, configure `YOUTUBE_PROXY_URL` or Webshare credentials.
6. Select a source from Recent Sources and ask a strict source question.
7. Generate flashcards and review one as Hard/Good/Easy.
8. Create a note from the composer and confirm it appears in Notes.
9. Delete a test source and confirm analytics refreshes.

## Common Issues

- YouTube fetch fails on Render: server IP is blocked by YouTube. Configure proxy env vars.
- OCR fails: install `tesseract-ocr` and `poppler-utils` on the backend host.
- No AI answer: configure `GROQ_API_KEY`; fallback mode will be less useful.
- Data disappears on free hosts: attach persistent disk or move from SQLite to a managed database.

## Product Limits

- SQLite is fine for a personal or demo product, but use PostgreSQL/pgvector for multi-user production.
- `EMBEDDING_BACKEND=hash` keeps startup cheap; transformer embeddings improve quality at higher resource cost.
- Session IDs isolate browser workspaces, but they are not a replacement for real login/authentication.
