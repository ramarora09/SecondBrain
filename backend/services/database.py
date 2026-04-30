"""SQLite persistence layer for the Second Brain backend."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterable


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "second_brain.db"
RUNTIME_DB_PATH = DATA_DIR / "second_brain_runtime.db"
TEMP_RUNTIME_DB_PATH = Path(tempfile.gettempdir()) / "second_brain_runtime.db"
ACTIVE_DB_PATH: Path | None = None


def _can_write_to_database(path: Path) -> bool:
    """Check whether a SQLite file can be written to."""
    try:
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE IF NOT EXISTS __db_write_probe (id INTEGER)")
        connection.commit()
        connection.execute("DROP TABLE IF EXISTS __db_write_probe")
        connection.commit()
        connection.close()
        return True
    except sqlite3.Error:
        return False


def _resolve_database_path() -> Path:
    """Choose a writable database path, falling back when the primary DB is locked."""
    global ACTIVE_DB_PATH

    if ACTIVE_DB_PATH is not None:
        return ACTIVE_DB_PATH

    configured_path = os.getenv("SECOND_BRAIN_DB_PATH")
    if configured_path:
        ACTIVE_DB_PATH = Path(configured_path)
        ACTIVE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return ACTIVE_DB_PATH

    if not DB_PATH.exists():
        ACTIVE_DB_PATH = DB_PATH
        return ACTIVE_DB_PATH

    if _can_write_to_database(DB_PATH):
        ACTIVE_DB_PATH = DB_PATH
        return ACTIVE_DB_PATH

    fallback_candidates = [RUNTIME_DB_PATH, TEMP_RUNTIME_DB_PATH]
    for candidate in fallback_candidates:
        if not candidate.exists():
            try:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(DB_PATH, candidate)
            except OSError:
                pass

        if _can_write_to_database(candidate):
            ACTIVE_DB_PATH = candidate
            return ACTIVE_DB_PATH

    ACTIVE_DB_PATH = TEMP_RUNTIME_DB_PATH
    return ACTIVE_DB_PATH


def initialize_database() -> None:
    """Create the SQLite database and required tables if they do not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                source_type TEXT NOT NULL,
                title TEXT NOT NULL,
                source_ref TEXT,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                topic TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                topic TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                memory_type TEXT NOT NULL DEFAULT 'fact',
                content TEXT NOT NULL,
                importance REAL NOT NULL DEFAULT 0.6,
                tags TEXT NOT NULL DEFAULT '[]',
                embedding TEXT NOT NULL DEFAULT '[]',
                source_message_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(source_message_id) REFERENCES chat_history(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                topic TEXT NOT NULL DEFAULT 'General',
                tags TEXT NOT NULL DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS note_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                source_note_id INTEGER NOT NULL,
                target_note_id INTEGER NOT NULL,
                relation_type TEXT NOT NULL DEFAULT 'related',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, source_note_id, target_note_id, relation_type),
                FOREIGN KEY(source_note_id) REFERENCES notes(id) ON DELETE CASCADE,
                FOREIGN KEY(target_note_id) REFERENCES notes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS learning_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                topics TEXT NOT NULL,
                current_index INTEGER NOT NULL DEFAULT 0,
                document_id INTEGER,
                document_title TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            );

            CREATE TABLE IF NOT EXISTS activity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                event_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                title TEXT NOT NULL,
                reason TEXT NOT NULL,
                action_prompt TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                chunk_id INTEGER,
                topic TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                ease_factor REAL NOT NULL DEFAULT 2.5,
                interval_days INTEGER NOT NULL DEFAULT 1,
                review_count INTEGER NOT NULL DEFAULT 0,
                next_review_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_review_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(chunk_id) REFERENCES chunks(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS graph_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                name TEXT NOT NULL UNIQUE,
                node_type TEXT NOT NULL DEFAULT 'concept',
                weight INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                source_node_id INTEGER NOT NULL,
                target_node_id INTEGER NOT NULL,
                weight INTEGER NOT NULL DEFAULT 1,
                UNIQUE(source_node_id, target_node_id),
                FOREIGN KEY(source_node_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY(target_node_id) REFERENCES graph_nodes(id) ON DELETE CASCADE
            );
            """
        )
        _ensure_column(cursor, "documents", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "chunks", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "chat_history", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "memories", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "notes", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "note_links", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "learning_sessions", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "activity_events", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "recommendations", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "flashcards", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "graph_nodes", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        _ensure_column(cursor, "graph_edges", "user_id", "TEXT NOT NULL DEFAULT 'anonymous'")
        connection.commit()


@contextmanager
def get_connection() -> Iterable[sqlite3.Connection]:
    """Yield a SQLite connection configured for dictionary-like row access."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(_resolve_database_path())
    connection.execute("PRAGMA foreign_keys = ON")
    connection.row_factory = sqlite3.Row

    try:
        yield connection
    finally:
        connection.close()


def _ensure_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    """Add a column to older SQLite databases without requiring manual migration."""
    existing_columns = {
        row["name"] if isinstance(row, sqlite3.Row) else row[1]
        for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing_columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def dumps_json(payload: Any) -> str:
    """Serialize Python data to a compact JSON string."""
    return json.dumps(payload, ensure_ascii=False)


def loads_json(payload: str, default: Any) -> Any:
    """Deserialize JSON with a safe default fallback."""
    try:
        return json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return default
