"""Routes for proactive assistant recommendations and activity."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from services.activity_service import get_activity
from services.analytics_service import get_analytics_summary
from services.session import normalize_user_id
from services.study_service import (
    build_study_recommendations,
    dismiss_recommendation,
    get_active_recommendations,
)

router = APIRouter()


@router.get("/recommendations")
def recommendations(x_session_id: str | None = Header(default=None)):
    """Return proactive next-action cards."""
    try:
        user_id = normalize_user_id(x_session_id)
        build_study_recommendations(get_analytics_summary(user_id=user_id), user_id=user_id)
        return {"recommendations": get_active_recommendations(user_id=user_id)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load recommendations: {exc}") from exc


@router.post("/recommendations/{recommendation_id}/dismiss")
def dismiss(recommendation_id: int, x_session_id: str | None = Header(default=None)):
    """Dismiss a recommendation."""
    if not dismiss_recommendation(recommendation_id, user_id=normalize_user_id(x_session_id)):
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {"message": "Recommendation dismissed"}


@router.get("/activity")
def activity(x_session_id: str | None = Header(default=None)):
    """Return recent activity timeline events."""
    try:
        return {"events": get_activity(user_id=normalize_user_id(x_session_id))}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load activity: {exc}") from exc
