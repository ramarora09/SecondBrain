"""Routes for structured notes."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from schemas import NoteCreateRequest, NoteUpdateRequest
from services.activity_service import record_activity
from services.notes_service import create_note, delete_note, get_note, list_notes, update_note
from services.session import normalize_user_id

router = APIRouter()


@router.get("/notes")
def notes(x_session_id: str | None = Header(default=None)):
    """Return notes for the current workspace."""
    try:
        return {"notes": list_notes(user_id=normalize_user_id(x_session_id))}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load notes: {exc}") from exc


@router.post("/notes")
def create(payload: NoteCreateRequest, x_session_id: str | None = Header(default=None)):
    """Create a note."""
    try:
        user_id = normalize_user_id(payload.user_id or x_session_id)
        note = create_note(
            title=payload.title,
            body=payload.body,
            topic=payload.topic,
            tags=payload.tags,
            user_id=user_id,
        )
        record_activity(
            user_id=user_id,
            event_type="note_created",
            entity_type="note",
            entity_id=note.get("id"),
            metadata={"title": note.get("title"), "topic": note.get("topic")},
        )
        return note
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create note: {exc}") from exc


@router.get("/notes/{note_id}")
def read(note_id: int, x_session_id: str | None = Header(default=None)):
    """Return one note."""
    note = get_note(note_id, user_id=normalize_user_id(x_session_id))
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.patch("/notes/{note_id}")
def patch(note_id: int, payload: NoteUpdateRequest, x_session_id: str | None = Header(default=None)):
    """Update one note."""
    note = update_note(
        note_id,
        title=payload.title,
        body=payload.body,
        topic=payload.topic,
        tags=payload.tags,
        user_id=normalize_user_id(x_session_id),
    )
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/notes/{note_id}")
def delete(note_id: int, x_session_id: str | None = Header(default=None)):
    """Delete one note."""
    deleted = delete_note(note_id, user_id=normalize_user_id(x_session_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"message": "Note deleted"}
