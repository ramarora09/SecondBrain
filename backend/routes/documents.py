"""Routes for managing indexed sources."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from schemas import DocumentUpdateRequest
from services.activity_service import record_activity
from services.session import normalize_user_id
from services.vector_store import (
    delete_document,
    get_document_content,
    get_documents,
    update_document_title,
)

router = APIRouter()


@router.get("/documents")
def list_indexed_documents(x_session_id: str | None = Header(default=None)):
    """Return indexed sources for the current session."""
    try:
        return {"documents": get_documents(limit=100, user_id=normalize_user_id(x_session_id))}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load documents: {exc}") from exc


@router.get("/documents/{document_id}")
def get_indexed_document(document_id: int, x_session_id: str | None = Header(default=None)):
    """Return a stored source including a short preview."""
    try:
        document = get_document_content(document_id, user_id=normalize_user_id(x_session_id))
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        content = document.pop("content", "")
        document["preview"] = content[:1200]
        document["character_count"] = len(content)
        return document
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load document: {exc}") from exc


@router.patch("/documents/{document_id}")
def rename_indexed_document(
    document_id: int,
    payload: DocumentUpdateRequest,
    x_session_id: str | None = Header(default=None),
):
    """Rename an indexed source."""
    user_id = normalize_user_id(x_session_id)
    try:
        document = update_document_title(document_id, payload.title, user_id=user_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        record_activity(
            user_id=user_id,
            event_type="document_renamed",
            entity_type="document",
            entity_id=document_id,
            metadata={"title": document["title"], "source_type": document["source_type"]},
        )
        return document
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not rename document: {exc}") from exc


@router.delete("/documents/{document_id}")
def delete_indexed_document(document_id: int, x_session_id: str | None = Header(default=None)):
    """Delete an indexed source and its chunks."""
    user_id = normalize_user_id(x_session_id)
    try:
        document = delete_document(document_id, user_id=user_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        record_activity(
            user_id=user_id,
            event_type="document_deleted",
            entity_type="document",
            entity_id=document_id,
            metadata={"title": document["title"], "source_type": document["source_type"]},
        )
        return {"message": "Document deleted", "document": document}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not delete document: {exc}") from exc
