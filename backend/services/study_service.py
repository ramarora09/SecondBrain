"""Study features: recommendations, flashcards, and spaced repetition."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.database import get_connection
from services.llm_service import generate_flashcards_with_llm, recommend_study_focus
from services.vector_store import get_chunk_samples


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _initial_review_time() -> str:
    """Make newly generated flashcards available for immediate review."""
    return _utcnow().isoformat()


def generate_flashcards(limit: int = 5, topic: str | None = None, user_id: str = "anonymous") -> list[dict]:
    """Generate and persist flashcards from recent chunks."""
    chunks = get_chunk_samples(limit=max(limit * 3, 10), topic=topic, user_id=user_id)
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
                INSERT INTO flashcards (user_id, chunk_id, topic, question, answer, next_review_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
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


def get_due_flashcards(limit: int = 20, user_id: str = "anonymous") -> list[dict]:
    """Return flashcards due for review."""
    now = _utcnow().isoformat()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, topic, question, answer, ease_factor, interval_days, review_count, next_review_at
            FROM flashcards
            WHERE user_id = ? AND (next_review_at IS NULL OR next_review_at <= ?)
            ORDER BY next_review_at ASC, created_at ASC
            LIMIT ?
            """,
            (user_id, now, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def review_flashcard(card_id: int, quality: int, user_id: str = "anonymous") -> dict | None:
    """Update a flashcard using a simple SM-2 style repetition rule."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM flashcards WHERE id = ? AND user_id = ?",
            (card_id, user_id),
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


def build_study_recommendations(analytics_summary: dict, user_id: str = "anonymous") -> dict:
    """Create actionable study guidance from analytics and flashcard load."""
    topic_counts = analytics_summary.get("topics", {})
    sorted_topics = sorted(topic_counts.items(), key=lambda item: item[1])
    weak_topics = [topic for topic, _ in sorted_topics[:3]] if sorted_topics else []
    due_count = len(get_due_flashcards(user_id=user_id))

    summary = {
        "topics": topic_counts,
        "weak_topics": weak_topics,
        "due_flashcards": due_count,
    }

    recent_documents = analytics_summary.get("recent_documents", [])
    cards: list[dict] = []

    if due_count:
        cards.append(
            {
                "title": "Review due flashcards",
                "reason": f"{due_count} flashcard{'s are' if due_count != 1 else ' is'} ready for spaced repetition.",
                "action_prompt": "Show my due flashcards and quiz me one by one.",
                "kind": "flashcards",
            }
        )

    if weak_topics:
        cards.append(
            {
                "title": f"Revise {weak_topics[0]}",
                "reason": "This is one of your least-practiced tracked topics.",
                "action_prompt": f"Give me a focused revision plan and practice quiz for {weak_topics[0]}.",
                "kind": "weak_topic",
            }
        )

    if recent_documents:
        latest = recent_documents[0]
        cards.append(
            {
                "title": "Summarize latest upload",
                "reason": f"You recently indexed {latest['title']}.",
                "action_prompt": "Summarize the active uploaded source with key points, examples, and revision notes.",
                "kind": "latest_source",
                "document_id": latest.get("id"),
            }
        )

    if not cards:
        cards.append(
            {
                "title": "Build your first knowledge source",
                "reason": "Upload a PDF, image, or YouTube link so the assistant can answer from your material.",
                "action_prompt": "Help me decide what to upload first for my learning goals.",
                "kind": "onboarding",
            }
        )

    _persist_recommendation_snapshot(cards, user_id=user_id)

    return {
        "weak_topics": weak_topics,
        "due_flashcards": due_count,
        "recommendation": recommend_study_focus(summary),
        "cards": cards[:3],
    }


def _persist_recommendation_snapshot(cards: list[dict], user_id: str) -> None:
    """Store active recommendation cards for API consumers."""
    with get_connection() as connection:
        connection.execute("DELETE FROM recommendations WHERE user_id = ? AND status = 'active'", (user_id,))
        connection.executemany(
            """
            INSERT INTO recommendations (user_id, title, reason, action_prompt, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            [(user_id, card["title"], card["reason"], card["action_prompt"]) for card in cards[:5]],
        )
        connection.commit()


def get_active_recommendations(user_id: str = "anonymous") -> list[dict]:
    """Return currently active persisted recommendations."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, reason, action_prompt, status, created_at
            FROM recommendations
            WHERE user_id = ? AND status = 'active'
            ORDER BY id DESC
            LIMIT 10
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def dismiss_recommendation(recommendation_id: int, user_id: str = "anonymous") -> bool:
    """Dismiss one recommendation."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE recommendations
            SET status = 'dismissed', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (recommendation_id, user_id),
        )
        connection.commit()
    return cursor.rowcount > 0
