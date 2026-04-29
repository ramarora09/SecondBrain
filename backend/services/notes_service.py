"""Structured note storage and search."""

from __future__ import annotations

from typing import Any

from services.database import dumps_json, get_connection, loads_json
from services.topic_classifier import detect_topic


def _normalize_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in tags or []:
        normalized = " ".join(str(tag).strip().split())
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(normalized[:40])
    return cleaned[:12]


def create_note(
    *,
    title: str,
    body: str = "",
    topic: str | None = None,
    tags: list[str] | None = None,
    user_id: str = "anonymous",
) -> dict[str, Any]:
    """Create a note and return it."""
    resolved_topic = topic or detect_topic(f"{title}\n{body}"[:2000])
    normalized_tags = _normalize_tags(tags)
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO notes (user_id, title, body, topic, tags)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, title.strip(), body.strip(), resolved_topic, dumps_json(normalized_tags)),
        )
        connection.commit()
        note_id = cursor.lastrowid
    return get_note(int(note_id), user_id=user_id) or {}


def list_notes(limit: int = 50, user_id: str = "anonymous") -> list[dict[str, Any]]:
    """Return recent notes."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, body, topic, tags, created_at, updated_at
            FROM notes
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [_row_to_note(row) for row in rows]


def get_note(note_id: int, user_id: str = "anonymous") -> dict[str, Any] | None:
    """Return one note."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, title, body, topic, tags, created_at, updated_at
            FROM notes
            WHERE id = ? AND user_id = ?
            LIMIT 1
            """,
            (note_id, user_id),
        ).fetchone()
    return _row_to_note(row) if row else None


def update_note(
    note_id: int,
    *,
    title: str | None = None,
    body: str | None = None,
    topic: str | None = None,
    tags: list[str] | None = None,
    user_id: str = "anonymous",
) -> dict[str, Any] | None:
    """Patch a note."""
    existing = get_note(note_id, user_id=user_id)
    if not existing:
        return None

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE notes
            SET title = ?, body = ?, topic = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (
                (title if title is not None else existing["title"]).strip(),
                (body if body is not None else existing["body"]).strip(),
                topic if topic is not None else existing["topic"],
                dumps_json(_normalize_tags(tags if tags is not None else existing["tags"])),
                note_id,
                user_id,
            ),
        )
        connection.commit()
    return get_note(note_id, user_id=user_id)


def delete_note(note_id: int, user_id: str = "anonymous") -> bool:
    """Delete a note."""
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
        connection.commit()
    return cursor.rowcount > 0


def _row_to_note(row: Any) -> dict[str, Any]:
    note = dict(row)
    note["tags"] = loads_json(note.get("tags"), [])
    return note
