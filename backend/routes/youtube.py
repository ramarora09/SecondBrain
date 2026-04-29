"""Routes for YouTube ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from schemas import YouTubeIngestRequest
from services.ingestion_service import ingest_youtube
from services.session import normalize_user_id

router = APIRouter()


@router.post("/upload-youtube")
def upload_youtube(payload: YouTubeIngestRequest, x_session_id: str | None = Header(default=None)):
    """Upload and index a YouTube transcript."""
    try:
        if not payload.url.strip():
            raise HTTPException(status_code=400, detail="Please provide a YouTube URL.")
        result = ingest_youtube(payload.url, user_id=normalize_user_id(payload.user_id or x_session_id))
        return {"message": "YouTube video processed", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"YouTube ingestion failed: {exc}") from exc
