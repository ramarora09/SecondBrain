"""Analytics routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from services.analytics_service import get_analytics_summary
from services.session import normalize_user_id
from services.study_service import build_study_recommendations

router = APIRouter()


@router.get("/analytics")
def analytics(x_session_id: str | None = Header(default=None)):
    """Return dashboard analytics and study recommendations."""
    try:
        user_id = normalize_user_id(x_session_id)
        summary = get_analytics_summary(user_id=user_id)
        summary["study_recommendations"] = build_study_recommendations(summary, user_id=user_id)
        return summary
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load analytics: {exc}") from exc
