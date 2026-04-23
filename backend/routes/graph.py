"""Knowledge graph routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.graph_service import get_graph_payload


router = APIRouter()


@router.get("/graph")
def get_graph():
    """Return extracted graph nodes and edges."""
    try:
        return get_graph_payload()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load knowledge graph: {exc}") from exc
