"""Analytics routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.analytics_service import get_analytics_summary
from services.study_service import build_study_recommendations

router = APIRouter()


@router.get("/analytics")
def analytics():
    """Return dashboard analytics and study recommendations."""
    try:
        summary = get_analytics_summary()
        summary["study_recommendations"] = build_study_recommendations(summary)
        return summary
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load analytics: {exc}") from exc
