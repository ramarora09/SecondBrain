"""Simple knowledge graph extraction and retrieval."""

from __future__ import annotations

import re
from collections import Counter
from itertools import combinations

from services.database import get_connection


DOMAIN_TERMS = {
    "python", "react", "fastapi", "sql", "database", "algorithm", "embedding",
    "retrieval", "frontend", "backend", "docker", "api", "memory", "vector",
    "analytics", "graph", "llm", "rag", "study", "knowledge",
}


def extract_entities(text: str, limit: int = 8) -> list[str]:
    """Extract lightweight entities from text without external NLP dependencies."""
    candidates = []
    candidates.extend(re.findall(r"\b[A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,})?\b", text))
    lowercase_words = re.findall(r"\b[a-z][a-zA-Z]{3,}\b", text.lower())
    candidates.extend(word for word in lowercase_words if word in DOMAIN_TERMS)

    stopwords = {"this", "that", "with", "from", "they", "have", "into", "your"}
    counts = Counter(item.strip() for item in candidates if item.strip().lower() not in stopwords)
    return [entity for entity, _ in counts.most_common(limit)]


def upsert_graph_from_text(text: str) -> None:
    """Extract entities from text and update the co-occurrence graph."""
    entities = extract_entities(text)
    if len(entities) < 2:
        return

    with get_connection() as connection:
        cursor = connection.cursor()
        node_ids: dict[str, int] = {}

        for entity in entities:
            cursor.execute(
                """
                INSERT INTO graph_nodes (name, node_type, weight)
                VALUES (?, 'concept', 1)
                ON CONFLICT(name) DO UPDATE SET weight = weight + 1
                """,
                (entity,),
            )
            node_id = cursor.execute(
                "SELECT id FROM graph_nodes WHERE name = ?",
                (entity,),
            ).fetchone()["id"]
            node_ids[entity] = int(node_id)

        for left, right in combinations(sorted(set(entities)), 2):
            source_node_id = node_ids[left]
            target_node_id = node_ids[right]
            if source_node_id == target_node_id:
                continue

            low_id, high_id = sorted((source_node_id, target_node_id))
            cursor.execute(
                """
                INSERT INTO graph_edges (source_node_id, target_node_id, weight)
                VALUES (?, ?, 1)
                ON CONFLICT(source_node_id, target_node_id)
                DO UPDATE SET weight = weight + 1
                """,
                (low_id, high_id),
            )

        connection.commit()


def get_graph_payload(limit: int = 100) -> dict:
    """Return graph nodes and edges formatted for the frontend."""
    with get_connection() as connection:
        nodes = connection.execute(
            """
            SELECT id, name, node_type, weight
            FROM graph_nodes
            ORDER BY weight DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        edges = connection.execute(
            """
            SELECT source_node_id, target_node_id, weight
            FROM graph_edges
            ORDER BY weight DESC
            LIMIT ?
            """,
            (limit * 2,),
        ).fetchall()

    return {
        "nodes": [dict(row) for row in nodes],
        "edges": [dict(row) for row in edges],
    }
