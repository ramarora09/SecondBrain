"""Knowledge graph routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from services.graph_service import get_graph_payload
from services.session import normalize_user_id


router = APIRouter()


@router.get("/graph")
def get_graph(x_session_id: str | None = Header(default=None)):
    """Return extracted graph nodes and edges."""
    try:
        return get_graph_payload(user_id=normalize_user_id(x_session_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load knowledge graph: {exc}") from exc
