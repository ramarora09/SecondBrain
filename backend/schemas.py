"""Shared request schemas for the API routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Question request payload."""

    question: str = Field(..., min_length=1)
    source: str = Field(default="all")
    topic: str | None = None
    language: str = Field(default="english")
    document_id: int | None = None


class YouTubeIngestRequest(BaseModel):
    """YouTube ingestion payload."""

    url: str = Field(..., min_length=5)


class FlashcardGenerateRequest(BaseModel):
    """Flashcard generation payload."""

    limit: int = Field(default=5, ge=1, le=20)
    topic: str | None = None


class FlashcardReviewRequest(BaseModel):
    """Spaced repetition review payload."""

    quality: int = Field(..., ge=1, le=5)
