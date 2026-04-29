"""Routes for durable personal memory."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from services.memory_store import add_memory_item, get_recent_memories, search_memories
from services.session import normalize_user_id

router = APIRouter()


@router.get("/memory")
def list_memory(x_session_id: str | None = Header(default=None)):
    """Return recent durable memories."""
    try:
        return {"memories": get_recent_memories(user_id=normalize_user_id(x_session_id))}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load memories: {exc}") from exc


@router.get("/memory/search")
def search_memory(q: str, x_session_id: str | None = Header(default=None)):
    """Search durable memories semantically."""
    try:
        return {"memories": search_memories(q, user_id=normalize_user_id(x_session_id))}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not search memories: {exc}") from exc


@router.post("/memory")
def create_memory(content: str, x_session_id: str | None = Header(default=None)):
    """Save a memory directly."""
    try:
        return add_memory_item(content, user_id=normalize_user_id(x_session_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not save memory: {exc}") from exc
