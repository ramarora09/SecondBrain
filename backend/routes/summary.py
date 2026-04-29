"""Knowledge summarization routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from services.llm_service import complete_text
from services.session import normalize_user_id
from services.vector_store import get_chunk_samples

router = APIRouter()


def _fallback_summary(chunks: list[dict]) -> str:
    """Return a lightweight summary when the LLM is unavailable."""
    bullets: list[str] = []
    for chunk in chunks[:5]:
        snippet = " ".join(chunk["chunk_text"].split())[:220].strip()
        if snippet:
            bullets.append(f"- {snippet}")
    return "\n".join(bullets) if bullets else "No summary could be generated."


@router.get("/summarize")
def summarize(topic: str | None = None, x_session_id: str | None = Header(default=None)):
    """Summarize recently stored knowledge."""
    context = ""
    try:
        chunks = get_chunk_samples(limit=20, topic=topic, user_id=normalize_user_id(x_session_id))
        if not chunks:
            raise HTTPException(status_code=404, detail="No stored knowledge found to summarize")

        context = "\n\n".join(chunk["chunk_text"] for chunk in chunks[:12])
        summary = complete_text(
            prompt=(
                "Summarize the following study material in concise bullet points.\n\n"
                f"{context[:5000]}"
            ),
            temperature=0.2,
        )
    except HTTPException:
        raise
    except Exception:
        summary = _fallback_summary(chunks)

    return {"summary": summary, "topic": topic or "all"}
