"""Advanced Chat, Memory, and AI Control Routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from schemas import AskRequest
from services.memory_store import (
    clear_memory,
    get_chat_history,
    reset_learning,
)
from services.rag_service import query_knowledge_base
from services.session import normalize_user_id


router = APIRouter()


# =========================
# 🔥 MAIN CHAT ENDPOINT
# =========================

@router.post("/ask")
def ask_question(payload: AskRequest, x_session_id: str | None = Header(default=None)):
    """Main AI query endpoint."""
    try:
        return query_knowledge_base(
            question=payload.question,
            source=payload.source,
            topic=payload.topic,
            language=payload.language,
            document_id=payload.document_id,
            user_id=normalize_user_id(payload.user_id or x_session_id),
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc


# =========================
# 🔥 GET SUPPORT (BACKWARD)
# =========================

@router.get("/ask")
def ask_question_get(
    q: str,
    source: str = "all",
    topic: str | None = None,
    language: str = "english",
    x_session_id: str | None = Header(default=None),
):
    try:
        return query_knowledge_base(
            question=q,
            source=source,
            topic=topic,
            language=language,
            user_id=normalize_user_id(x_session_id),
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}") from exc


# =========================
# 🔥 CHAT HISTORY
# =========================

@router.get("/history")
def get_history(x_session_id: str | None = Header(default=None)):
    try:
        return {"messages": get_chat_history(user_id=normalize_user_id(x_session_id))}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load chat history: {exc}") from exc


@router.delete("/history")
def delete_history(x_session_id: str | None = Header(default=None)):
    try:
        clear_memory(user_id=normalize_user_id(x_session_id))
        return {"message": "Chat history cleared"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not clear chat history: {exc}") from exc


# =========================
# 🔥 STUDY ANALYTICS
# =========================

# =========================
# 🔥 RESET LEARNING FLOW
# =========================

@router.post("/reset-learning")
def reset_learning_flow(x_session_id: str | None = Header(default=None)):
    try:
        reset_learning(normalize_user_id(x_session_id))
        return {"message": "Learning flow reset"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Reset failed: {exc}") from exc
