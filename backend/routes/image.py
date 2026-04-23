"""Routes for OCR extraction."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from services.ingestion_service import ingest_image

router = APIRouter()


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """Extract text from an uploaded image with OCR fallback messaging."""
    try:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Please upload a valid image file.")
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded image is empty.")
        result = ingest_image(contents, file.filename or "uploaded-image")
        return {"message": "Image processed successfully", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image processing failed: {exc}") from exc
