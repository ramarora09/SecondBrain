"""Activity timeline helpers for proactive intelligence."""

from __future__ import annotations

from typing import Any

from services.database import dumps_json, get_connection, loads_json


def record_activity(
    *,
    user_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str | int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist a lightweight event for timelines and recommendations."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO activity_events (user_id, event_type, entity_type, entity_id, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, event_type, entity_type, str(entity_id) if entity_id is not None else None, dumps_json(metadata or {})),
        )
        connection.commit()


def get_activity(limit: int = 25, user_id: str = "anonymous") -> list[dict[str, Any]]:
    """Return recent activity events."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, event_type, entity_type, entity_id, metadata, created_at
            FROM activity_events
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    events: list[dict[str, Any]] = []
    for row in rows:
        event = dict(row)
        event["metadata"] = loads_json(event.get("metadata"), {})
        events.append(event)
    return events
