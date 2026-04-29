"""Advanced persistent chat memory, durable memories, and learning flow."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from services.database import dumps_json, get_connection, loads_json
from services.embeddings import embed_query

MEMORY_PREFIXES = ("remember this", "remember:", "save this", "save memory")


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    left_vector = np.asarray(left, dtype=np.float32)
    right_vector = np.asarray(right, dtype=np.float32)
    if left_vector.size == 0 or right_vector.size == 0 or left_vector.shape != right_vector.shape:
        return 0.0
    left_norm = np.linalg.norm(left_vector)
    right_norm = np.linalg.norm(right_vector)
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return float(np.dot(left_vector / left_norm, right_vector / right_norm))


def wants_to_remember(text: str) -> bool:
    """Return whether a user message is an explicit memory command."""
    normalized = text.lower().strip()
    return any(normalized.startswith(prefix) for prefix in MEMORY_PREFIXES)


def _strip_memory_command(text: str) -> str:
    cleaned = text.strip()
    for prefix in MEMORY_PREFIXES:
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].lstrip(" :-")
            break
    return cleaned.strip()


def infer_memory_tags(content: str) -> list[str]:
    """Infer simple tags for memory organization."""
    lowered = content.lower()
    tags: list[str] = []
    for raw_tag, label in {
        "dsa": "DSA",
        "data structure": "DSA",
        "algorithm": "DSA",
        "ai": "AI",
        "machine learning": "ML",
        "ml": "ML",
        "backend": "Backend",
        "frontend": "Frontend",
        "project": "Project",
        "internship": "Internship",
        "interview": "Interview",
    }.items():
        if raw_tag in lowered and label not in tags:
            tags.append(label)
    return tags or ["General"]


def add_memory_item(
    content: str,
    *,
    user_id: str = "anonymous",
    memory_type: str = "fact",
    importance: float = 0.7,
    tags: list[str] | None = None,
    source_message_id: int | None = None,
) -> dict[str, Any]:
    """Persist a durable memory with an embedding."""
    cleaned = _strip_memory_command(content)
    if not cleaned:
        raise ValueError("Memory content cannot be empty")

    resolved_tags = tags or infer_memory_tags(cleaned)
    embedding = embed_query(cleaned)
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO memories (user_id, memory_type, content, importance, tags, embedding, source_message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                memory_type,
                cleaned,
                float(max(0.0, min(1.0, importance))),
                dumps_json(resolved_tags),
                dumps_json(embedding),
                source_message_id,
            ),
        )
        connection.commit()
        memory_id = cursor.lastrowid

    return {
        "id": int(memory_id),
        "content": cleaned,
        "type": memory_type,
        "importance": importance,
        "tags": resolved_tags,
    }


def search_memories(query: str, *, limit: int = 5, user_id: str = "anonymous") -> list[dict[str, Any]]:
    """Semantically recall durable memories."""
    query_embedding = embed_query(query)
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, memory_type, content, importance, tags, embedding, created_at
            FROM memories
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 200
            """,
            (user_id,),
        ).fetchall()

    results: list[dict[str, Any]] = []
    query_terms = {term for term in re.findall(r"[a-zA-Z0-9+#-]{3,}", query.lower())}
    for row in rows:
        memory = dict(row)
        embedding = loads_json(memory.pop("embedding"), [])
        semantic_score = _cosine_similarity(query_embedding, embedding)
        memory_terms = {term for term in re.findall(r"[a-zA-Z0-9+#-]{3,}", memory["content"].lower())}
        lexical_score = len(query_terms & memory_terms) / max(len(query_terms), 1) if query_terms else 0.0
        memory["tags"] = loads_json(memory.get("tags"), [])
        memory["score"] = round((semantic_score * 0.75) + (lexical_score * 0.25), 4)
        if memory["score"] > 0.05 or lexical_score > 0:
            results.append(memory)

    results.sort(key=lambda item: (item["score"], item["importance"]), reverse=True)
    return results[:limit]


def get_recent_memories(limit: int = 20, user_id: str = "anonymous") -> list[dict[str, Any]]:
    """Return saved memories for the memory panel."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, memory_type, content, importance, tags, created_at
            FROM memories
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    memories = []
    for row in rows:
        memory = dict(row)
        memory["tags"] = loads_json(memory.get("tags"), [])
        memories.append(memory)
    return memories


def get_memories_from_yesterday(user_id: str = "anonymous") -> list[dict[str, Any]]:
    """Return memories saved yesterday in UTC."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=1)
    end = today
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, memory_type, content, importance, tags, created_at
            FROM memories
            WHERE user_id = ?
              AND date(created_at) >= date(?)
              AND date(created_at) < date(?)
            ORDER BY id ASC
            """,
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchall()

    memories = []
    for row in rows:
        memory = dict(row)
        memory["tags"] = loads_json(memory.get("tags"), [])
        memories.append(memory)
    return memories


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
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO learning_sessions (user_id, topics, current_index, document_id, document_title, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            ON CONFLICT(user_id) DO UPDATE SET
                topics = excluded.topics,
                current_index = excluded.current_index,
                document_id = excluded.document_id,
                document_title = excluded.document_title,
                status = 'active',
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                dumps_json(topics),
                max(0, min(start_index, len(topics))),
                document_id,
                document_title,
            ),
        )
        connection.commit()


def get_next_topic(user_id: str) -> dict | None:
    """Get next learning step with active document context."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT topics, current_index, document_id, document_title
            FROM learning_sessions
            WHERE user_id = ? AND status = 'active'
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    data = dict(row)
    topics = loads_json(data["topics"], [])
    current_index = int(data["current_index"])
    if current_index >= len(topics):
        return {
            "text": "All topics completed. Great job!",
            "document_id": data.get("document_id"),
            "document_title": data.get("document_title"),
            "completed": True,
        }

    topic = topics[current_index]
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE learning_sessions
            SET current_index = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (current_index + 1, user_id),
        )
        connection.commit()
    return {
        "text": f"Next Topic:\n{topic}",
        "document_id": data.get("document_id"),
        "document_title": data.get("document_title"),
        "completed": False,
    }


def reset_learning(user_id: str) -> None:
    """Reset topic flow."""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE learning_sessions
            SET status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user_id,),
        )
        connection.commit()


def get_study_summary(user_id: str = "anonymous") -> dict:
    """Return full study analytics."""
    return {
        "total_questions": get_question_count(user_id=user_id),
        "topics": get_topic_counts(user_id=user_id),
        "weak_topics": get_weak_topics(user_id=user_id),
    }
