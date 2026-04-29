"""Advanced persistent chat memory + learning flow."""

from __future__ import annotations

from services.database import get_connection

topic_flow = {}


def add_to_memory(question: str, answer: str, topic: str, user_id: str = "anonymous") -> None:
    """Persist a question-answer pair."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_history (user_id, question, answer, topic)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, question, answer, topic),
        )
        connection.commit()


def get_memory(limit: int = 3, user_id: str = "anonymous") -> list[dict]:
    """Return latest Q/A pairs."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT question, answer, topic, created_at
            FROM chat_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    return [dict(row) for row in reversed(rows)]


def get_chat_history(limit: int = 100, user_id: str = "anonymous") -> list[dict]:
    """Return chat history formatted for UI."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT question, answer, topic, created_at
            FROM chat_history
            WHERE user_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    messages: list[dict] = []
    for row in rows:
        messages.append(
            {
                "role": "user",
                "text": row["question"],
                "created_at": row["created_at"],
            }
        )
        messages.append(
            {
                "role": "assistant",
                "text": row["answer"],
                "topic": row["topic"],
                "created_at": row["created_at"],
            }
        )

    return messages


def clear_memory(user_id: str = "anonymous") -> None:
    """Clear stored chat history."""
    with get_connection() as connection:
        connection.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        connection.commit()


def get_question_count(user_id: str = "anonymous") -> int:
    """Return total number of stored questions."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM chat_history WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["count"]) if row else 0


def get_topic_counts(user_id: str = "anonymous") -> dict[str, int]:
    """Return topic frequencies from chat history."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT topic, COUNT(*) AS count
            FROM chat_history
            WHERE user_id = ?
            GROUP BY topic
            ORDER BY count DESC
            """
            ,
            (user_id,),
        ).fetchall()

    return {row["topic"]: int(row["count"]) for row in rows}


def get_weak_topics(limit: int = 3, user_id: str = "anonymous") -> list[str]:
    """Detect weak topics (least asked)."""
    topic_counts = get_topic_counts(user_id=user_id)
    if not topic_counts:
        return []

    sorted_topics = sorted(topic_counts.items(), key=lambda item: item[1])
    return [topic for topic, _ in sorted_topics[:limit]]


def start_topic(
    user_id: str,
    topics: list[str],
    document_id: int | None = None,
    document_title: str | None = None,
    start_index: int = 0,
) -> None:
    """Start structured learning for a specific document context."""
    topic_flow[user_id] = {
        "topics": topics,
        "index": max(0, min(start_index, len(topics))),
        "document_id": document_id,
        "document_title": document_title,
    }


def get_next_topic(user_id: str) -> dict | None:
    """Get next learning step with active document context."""
    if user_id not in topic_flow:
        return None

    data = topic_flow[user_id]
    if data["index"] >= len(data["topics"]):
        return {
            "text": "All topics completed. Great job!",
            "document_id": data.get("document_id"),
            "document_title": data.get("document_title"),
            "completed": True,
        }

    topic = data["topics"][data["index"]]
    data["index"] += 1
    return {
        "text": f"Next Topic:\n{topic}",
        "document_id": data.get("document_id"),
        "document_title": data.get("document_title"),
        "completed": False,
    }


def reset_learning(user_id: str) -> None:
    """Reset topic flow."""
    if user_id in topic_flow:
        del topic_flow[user_id]


def get_study_summary(user_id: str = "anonymous") -> dict:
    """Return full study analytics."""
    return {
        "total_questions": get_question_count(user_id=user_id),
        "topics": get_topic_counts(user_id=user_id),
        "weak_topics": get_weak_topics(user_id=user_id),
    }
