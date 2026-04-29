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
    user_id: str | None = None
    strict: bool = False


class YouTubeIngestRequest(BaseModel):
    """YouTube ingestion payload."""

    url: str = Field(..., min_length=5)
    user_id: str | None = None


class FlashcardGenerateRequest(BaseModel):
    """Flashcard generation payload."""

    limit: int = Field(default=5, ge=1, le=20)
    topic: str | None = None
    user_id: str | None = None


class FlashcardReviewRequest(BaseModel):
    """Spaced repetition review payload."""

    quality: int = Field(..., ge=1, le=5)


class NoteCreateRequest(BaseModel):
    """Create a structured note."""

    title: str = Field(..., min_length=1, max_length=180)
    body: str = Field(default="")
    topic: str = Field(default="General")
    tags: list[str] = Field(default_factory=list)
    user_id: str | None = None


class NoteUpdateRequest(BaseModel):
    """Update a structured note."""

    title: str | None = Field(default=None, max_length=180)
    body: str | None = None
    topic: str | None = None
    tags: list[str] | None = None
