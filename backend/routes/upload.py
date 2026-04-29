"""Routes for file ingestion."""

from __future__ import annotations

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from services.ingestion_service import ingest_pdf
from services.session import normalize_user_id

router = APIRouter()


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), x_session_id: str | None = Header(default=None)):
    """Upload and index a PDF document."""
    try:
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Please upload a valid PDF file.")
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")
        result = ingest_pdf(contents, file.filename or "uploaded.pdf", user_id=normalize_user_id(x_session_id))
        return {"message": "PDF processed successfully", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF upload failed: {exc}") from exc
