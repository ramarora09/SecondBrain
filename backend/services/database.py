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
                source_type TEXT NOT NULL,
                title TEXT NOT NULL,
                source_ref TEXT,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                topic TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                name TEXT NOT NULL UNIQUE,
                node_type TEXT NOT NULL DEFAULT 'concept',
                weight INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_node_id INTEGER NOT NULL,
                target_node_id INTEGER NOT NULL,
                weight INTEGER NOT NULL DEFAULT 1,
                UNIQUE(source_node_id, target_node_id),
                FOREIGN KEY(source_node_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY(target_node_id) REFERENCES graph_nodes(id) ON DELETE CASCADE
            );
            """
        )
        connection.commit()


@contextmanager
def get_connection() -> Iterable[sqlite3.Connection]:
    """Yield a SQLite connection configured for dictionary-like row access."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(_resolve_database_path())
    connection.row_factory = sqlite3.Row

    try:
        yield connection
    finally:
        connection.close()


def dumps_json(payload: Any) -> str:
    """Serialize Python data to a compact JSON string."""
    return json.dumps(payload, ensure_ascii=False)


def loads_json(payload: str, default: Any) -> Any:
    """Deserialize JSON with a safe default fallback."""
    try:
        return json.loads(payload)
    except (TypeError, json.JSONDecodeError):
        return default
