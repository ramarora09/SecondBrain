"""Topic detection helpers for analytics and retrieval."""

from __future__ import annotations

from services.llm_service import classify_topic_with_llm


TOPIC_RULES = {
    "DSA": ["algorithm", "data structure", "dynamic programming", "graph", "tree", "array", "stack", "queue"],
    "OS": ["operating system", "thread", "process", "cpu scheduling", "deadlock", "paging", "os"],
    "DBMS": ["database", "sql", "dbms", "normalization", "transaction", "index", "join"],
    "AI/ML": ["model", "llm", "machine learning", "neural", "embedding", "rag", "ai"],
    "Backend": ["fastapi", "api", "python", "server", "backend", "authentication"],
    "Frontend": ["react", "tailwind", "ui", "frontend", "javascript", "css"],
    "DevOps": ["docker", "deploy", "ci", "cd", "kubernetes", "devops", "pipeline"],
}


def detect_topic(text: str) -> str:
    """Detect a best-effort topic label from text."""
    normalized = text.lower()
    best_topic = "General"
    best_score = 0

    for topic, keywords in TOPIC_RULES.items():
        score = sum(1 for keyword in keywords if keyword in normalized)
        if score > best_score:
            best_topic = topic
            best_score = score

    if best_score > 0:
        return best_topic

    llm_label = classify_topic_with_llm(text, list(TOPIC_RULES.keys()))
    return llm_label or "General"
