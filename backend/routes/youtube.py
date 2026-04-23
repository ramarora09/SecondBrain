"""Routes for YouTube ingestion."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from schemas import YouTubeIngestRequest
from services.ingestion_service import ingest_youtube

router = APIRouter()


@router.post("/upload-youtube")
def upload_youtube(payload: YouTubeIngestRequest):
    """Upload and index a YouTube transcript."""
    try:
        if not payload.url.strip():
            raise HTTPException(status_code=400, detail="Please provide a YouTube URL.")
        result = ingest_youtube(payload.url)
        return {"message": "YouTube video processed", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"YouTube ingestion failed: {exc}") from exc
