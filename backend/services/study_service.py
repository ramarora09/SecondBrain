"""Study features: recommendations, flashcards, and spaced repetition."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.database import get_connection
from services.llm_service import generate_flashcards_with_llm, recommend_study_focus
from services.vector_store import get_chunk_samples


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _initial_review_time() -> str:
    """Schedule new flashcards for the next day instead of immediately."""
    return (_utcnow() + timedelta(days=1)).isoformat()


def generate_flashcards(limit: int = 5, topic: str | None = None) -> list[dict]:
    """Generate and persist flashcards from recent chunks."""
    chunks = get_chunk_samples(limit=max(limit * 3, 10), topic=topic)
    if not chunks:
        return []

    source_text = "\n\n".join(chunk["chunk_text"] for chunk in chunks[:10])
    primary_topic = topic or chunks[0]["topic"]
    cards = generate_flashcards_with_llm(primary_topic, source_text, limit)

    if not cards:
        cards = []
        for chunk in chunks[:limit]:
            excerpt = chunk["chunk_text"].split(".")[0].strip()
            if excerpt:
                cards.append(
                    {
                        "question": f"What is a key idea from {chunk['title']} about {chunk['topic']}?",
                        "answer": excerpt,
                        "chunk_id": chunk["id"],
                        "topic": chunk["topic"],
                    }
                )

    persisted: list[dict] = []
    with get_connection() as connection:
        cursor = connection.cursor()
        for index, card in enumerate(cards[:limit]):
            chunk_ref = chunks[min(index, len(chunks) - 1)]
            scheduled_review = _initial_review_time()
            cursor.execute(
                """
                INSERT INTO flashcards (chunk_id, topic, question, answer, next_review_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    chunk_ref["id"],
                    card.get("topic") or chunk_ref["topic"],
                    card["question"],
                    card["answer"],
                    scheduled_review,
                ),
            )
            persisted.append(
                {
                    "id": cursor.lastrowid,
                    "topic": card.get("topic") or chunk_ref["topic"],
                    "question": card["question"],
                    "answer": card["answer"],
                    "next_review_at": scheduled_review,
                    "status": "scheduled",
                }
            )
        connection.commit()

    return persisted


def get_due_flashcards(limit: int = 20) -> list[dict]:
    """Return flashcards due for review."""
    now = _utcnow().isoformat()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, topic, question, answer, ease_factor, interval_days, review_count, next_review_at
            FROM flashcards
            WHERE next_review_at IS NULL OR next_review_at <= ?
            ORDER BY next_review_at ASC, created_at ASC
            LIMIT ?
            """,
            (now, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def review_flashcard(card_id: int, quality: int) -> dict | None:
    """Update a flashcard using a simple SM-2 style repetition rule."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM flashcards WHERE id = ?",
            (card_id,),
        ).fetchone()

        if row is None:
            return None

        ease_factor = max(1.3, float(row["ease_factor"]) + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        review_count = int(row["review_count"]) + 1

        if quality < 3:
            interval_days = 1
        elif review_count == 1:
            interval_days = 1
        elif review_count == 2:
            interval_days = 3
        else:
            interval_days = max(1, int(round(row["interval_days"] * ease_factor)))

        next_review_at = (_utcnow() + timedelta(days=interval_days)).isoformat()

        connection.execute(
            """
            UPDATE flashcards
            SET ease_factor = ?, interval_days = ?, review_count = ?, last_review_at = ?, next_review_at = ?
            WHERE id = ?
            """,
            (ease_factor, interval_days, review_count, _utcnow().isoformat(), next_review_at, card_id),
        )
        connection.commit()

    return {
        "id": card_id,
        "ease_factor": ease_factor,
        "interval_days": interval_days,
        "review_count": review_count,
        "next_review_at": next_review_at,
    }


def build_study_recommendations(analytics_summary: dict) -> dict:
    """Create actionable study guidance from analytics and flashcard load."""
    topic_counts = analytics_summary.get("topics", {})
    sorted_topics = sorted(topic_counts.items(), key=lambda item: item[1])
    weak_topics = [topic for topic, _ in sorted_topics[:3]] if sorted_topics else []
    due_count = len(get_due_flashcards())

    summary = {
        "topics": topic_counts,
        "weak_topics": weak_topics,
        "due_flashcards": due_count,
    }

    return {
        "weak_topics": weak_topics,
        "due_flashcards": due_count,
        "recommendation": recommend_study_focus(summary),
    }
