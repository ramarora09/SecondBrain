"""Study routes for flashcards and recommendations."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from schemas import FlashcardGenerateRequest, FlashcardReviewRequest
from services.analytics_service import get_analytics_summary
from services.session import normalize_user_id
from services.study_service import (
    build_study_recommendations,
    generate_flashcards,
    get_due_flashcards,
    review_flashcard,
)


router = APIRouter()


@router.get("/study/recommendations")
def get_study_recommendations(x_session_id: str | None = Header(default=None)):
    """Return personalized study recommendations."""
    try:
        user_id = normalize_user_id(x_session_id)
        return build_study_recommendations(get_analytics_summary(user_id=user_id), user_id=user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load study recommendations: {exc}") from exc


@router.post("/study/flashcards")
def create_flashcards(payload: FlashcardGenerateRequest, x_session_id: str | None = Header(default=None)):
    """Generate flashcards from stored knowledge."""
    cards = generate_flashcards(
        limit=payload.limit,
        topic=payload.topic,
        user_id=normalize_user_id(payload.user_id or x_session_id),
    )
    if not cards:
        raise HTTPException(status_code=404, detail="No chunks available to generate flashcards")
    return {"flashcards": cards}


@router.get("/study/flashcards/due")
def due_flashcards(x_session_id: str | None = Header(default=None)):
    """Return due flashcards for spaced repetition."""
    try:
        return {"flashcards": get_due_flashcards(user_id=normalize_user_id(x_session_id))}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load flashcards: {exc}") from exc


@router.post("/study/flashcards/{card_id}/review")
def review(card_id: int, payload: FlashcardReviewRequest, x_session_id: str | None = Header(default=None)):
    """Review a flashcard using a simple spaced repetition rule."""
    result = review_flashcard(card_id, payload.quality, user_id=normalize_user_id(x_session_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Flashcard not found")
    return result
