"""Persistent vector storage backed by SQLite."""

from __future__ import annotations

from typing import Any

import numpy as np

from services.database import dumps_json, get_connection, loads_json


def store_document(
    *,
    user_id: str = "anonymous",
    source_type: str,
    title: str,
    source_ref: str | None,
    topic: str,
    content: str,
    chunks: list[str],
    embeddings: list[list[float]] | np.ndarray,
    metadata: dict[str, Any] | None = None,
) -> int:
    """Persist a document and its chunk embeddings."""
    serialized_embeddings = np.asarray(embeddings, dtype=np.float32).tolist()
    metadata = metadata or {}

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO documents (user_id, source_type, title, source_ref, topic, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, source_type, title, source_ref, topic, content),
        )
        document_id = cursor.lastrowid

        chunk_rows = []
        for chunk_index, (chunk_text, embedding) in enumerate(zip(chunks, serialized_embeddings)):
            chunk_metadata = {
                **metadata,
                "source_type": source_type,
                "topic": topic,
                "title": title,
                "source_ref": source_ref,
                "chunk_index": chunk_index,
            }
            chunk_rows.append(
                (
                    document_id,
                    user_id,
                    chunk_index,
                    chunk_text,
                    dumps_json(embedding),
                    topic,
                    dumps_json(chunk_metadata),
                )
            )

        cursor.executemany(
            """
            INSERT INTO chunks (document_id, user_id, chunk_index, chunk_text, embedding, topic, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            chunk_rows,
        )

        connection.commit()

    return int(document_id)


def search_chunks(
    query_embedding: list[float] | np.ndarray,
    *,
    source_filter: str = "all",
    topic_filter: str | None = None,
    document_id_filter: int | None = None,
    user_id: str = "anonymous",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return the most similar chunks using cosine similarity."""
    query_vector = np.asarray(query_embedding, dtype=np.float32)
    norm = np.linalg.norm(query_vector)
    if norm == 0:
        return []
    query_vector = query_vector / norm

    sql = """
        SELECT chunks.id, chunks.document_id, chunks.chunk_index, chunks.chunk_text, chunks.embedding,
               chunks.topic, chunks.metadata,
               documents.title, documents.source_type, documents.source_ref
        FROM chunks
        JOIN documents ON documents.id = chunks.document_id
        WHERE 1 = 1
        AND documents.user_id = ?
    """
    params: list[Any] = [user_id]

    if source_filter != "all":
        sql += " AND documents.source_type = ?"
        params.append(source_filter)

    if topic_filter:
        sql += " AND chunks.topic = ?"
        params.append(topic_filter)

    if document_id_filter is not None:
        sql += " AND chunks.document_id = ?"
        params.append(document_id_filter)

    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        embedding = np.asarray(loads_json(row["embedding"], []), dtype=np.float32)
        if embedding.size == 0:
            continue
        if embedding.shape != query_vector.shape:
            continue

        embedding_norm = np.linalg.norm(embedding)
        if embedding_norm == 0:
            continue

        similarity = float(np.dot(query_vector, embedding / embedding_norm))
        metadata = loads_json(row["metadata"], {})
        metadata.setdefault("title", row["title"])
        metadata.setdefault("source_type", row["source_type"])
        metadata.setdefault("source_ref", row["source_ref"])
        metadata.setdefault("chunk_index", row["chunk_index"])

        results.append(
            {
                "chunk_id": row["id"],
                "document_id": row["document_id"],
                "text": row["chunk_text"],
                "topic": row["topic"],
                "score": similarity,
                "metadata": metadata,
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def get_documents(limit: int = 100, user_id: str = "anonymous") -> list[dict[str, Any]]:
    """Return recent uploaded documents."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, source_type, title, source_ref, topic, created_at
            FROM documents
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def get_latest_document(user_id: str = "anonymous") -> dict[str, Any] | None:
    """Return the most recently uploaded document."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, source_type, title, source_ref, topic, created_at
            FROM documents
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """
            ,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_document_by_id(document_id: int, user_id: str = "anonymous") -> dict[str, Any] | None:
    """Return a specific uploaded document by id."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, source_type, title, source_ref, topic, created_at
            FROM documents
            WHERE id = ? AND user_id = ?
            LIMIT 1
            """,
            (document_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def get_document_content(document_id: int, user_id: str = "anonymous") -> dict[str, Any] | None:
    """Return a specific uploaded document including stored content."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, source_type, title, source_ref, topic, content, created_at
            FROM documents
            WHERE id = ? AND user_id = ?
            LIMIT 1
            """,
            (document_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def get_document_count(user_id: str = "anonymous") -> int:
    """Return the number of uploaded documents."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM documents WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return int(row["count"]) if row else 0


def get_chunk_samples(limit: int = 50, topic: str | None = None, user_id: str = "anonymous") -> list[dict[str, Any]]:
    """Return stored chunks for summarization and flashcard generation."""
    sql = """
        SELECT chunks.id, chunks.chunk_text, chunks.topic, documents.title, documents.source_type
        FROM chunks
        JOIN documents ON documents.id = chunks.document_id
        WHERE chunks.user_id = ?
    """
    params: list[Any] = [user_id]
    if topic:
        sql += " AND chunks.topic = ?"
        params.append(topic)

    sql += " ORDER BY chunks.created_at DESC LIMIT ?"
    params.append(limit)

    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()

    return [dict(row) for row in rows]


def get_document_chunks(document_id: int, limit: int = 40, user_id: str = "anonymous") -> list[dict[str, Any]]:
    """Return stored chunks for a specific document."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT chunks.id, chunks.chunk_text, chunks.topic, documents.title, documents.source_type
            FROM chunks
            JOIN documents ON documents.id = chunks.document_id
            WHERE documents.id = ? AND documents.user_id = ?
            ORDER BY chunks.chunk_index ASC
            LIMIT ?
            """,
            (document_id, user_id, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def reset_store() -> None:
    """Clear persisted documents, chunks, flashcards, and graph data."""
    with get_connection() as connection:
        connection.execute("DELETE FROM flashcards")
        connection.execute("DELETE FROM graph_edges")
        connection.execute("DELETE FROM graph_nodes")
        connection.execute("DELETE FROM chunks")
        connection.execute("DELETE FROM documents")
        connection.commit()
