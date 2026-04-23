"""Production-style retrieval augmented generation flow with intelligence layer."""

from __future__ import annotations

from services.embeddings import embed_query
from services.llm_service import answer_question, complete_text
from services.memory_store import add_to_memory, get_memory, get_next_topic, start_topic
from services.topic_classifier import detect_topic
from services.vector_store import get_document_by_id, get_latest_document, search_chunks


def _format_context(results: list[dict]) -> list[str]:
    """Convert retrieval results into compact prompt sections."""
    sections: list[str] = []
    for item in results:
        metadata = item.get("metadata", {})
        title = metadata.get("title", "Untitled source")
        source_type = metadata.get("source_type", "source")
        chunk_index = metadata.get("chunk_index", 0)
        cleaned_text = " ".join(item["text"].split())

        sections.append(
            (
                f"Source: {title}\n"
                f"Type: {source_type}\n"
                f"Topic: {item.get('topic', 'General')}\n"
                f"Chunk: {chunk_index}\n"
                f"Similarity: {item['score']:.3f}\n"
                f"Content: {cleaned_text}"
            )
        )

    return sections


def _select_relevant_results(results: list[dict], limit: int = 6) -> list[dict]:
    """Keep only the strongest retrieval matches for prompting."""
    if not results:
        return []

    filtered = [item for item in results if item.get("score", 0.0) >= 0.12]
    if not filtered:
        filtered = results[:2]

    return filtered[:limit]


def detect_intent(question: str) -> str:
    """Infer the interaction intent from the question text."""
    q = question.lower()

    if "next" in q:
        return "next"
    if "teach" in q or "start" in q:
        return "teaching"
    if "summarize" in q:
        return "summary"
    if "revise" in q:
        return "revision"
    return "qa"


def generate_topics(question: str) -> list[str]:
    """Break a learning request into ordered study topics."""
    prompt = f"""
Break this topic into step-by-step learning topics.

Topic:
{question}

Return only a numbered list.
"""
    response = complete_text(prompt=prompt)

    topics: list[str] = []
    for line in response.splitlines():
        cleaned = line.strip()
        if cleaned:
            topics.append(cleaned)

    return topics


def _memory_context_lines(limit: int = 3) -> list[str]:
    return [f"Q: {item['question']}\nA: {item['answer']}" for item in get_memory(limit=limit)]


def _fallback_answer(language: str) -> str:
    if language.lower() == "hinglish":
        return (
            "Mujhe abhi relevant context nahi mila. Pehle PDF, image, ya YouTube source upload karo, "
            "ya thoda specific question poochho."
        )
    return "I could not find relevant context yet. Upload a PDF, image, or YouTube source, or ask a more specific question."


def query_knowledge_base(
    question: str,
    source: str = "all",
    topic: str | None = None,
    language: str = "english",
    document_id: int | None = None,
) -> dict:
    """Answer a question using retrieved knowledge, memory, and learning flow."""
    question = question.strip()
    if not question:
        raise ValueError("Question cannot be empty")

    intent = detect_intent(question)

    if intent == "next":
        next_topic = get_next_topic("user1")
        return {
            "question": question,
            "answer": next_topic["text"] if next_topic else "No active topic. Start a topic first.",
            "topic": "learning_flow",
            "language": language,
            "sources": [],
            "has_context": False,
            "document_id": next_topic.get("document_id") if next_topic else document_id,
            "document_title": next_topic.get("document_title") if next_topic else None,
        }

    if intent == "teaching":
        active_document = get_document_by_id(document_id) if document_id is not None else get_latest_document()
        topics = generate_topics(question)
        start_topic(
            "user1",
            topics,
            document_id=active_document.get("id") if active_document else None,
            document_title=active_document.get("title") if active_document else None,
        )
        first_topic = topics[0] if topics else question
        return {
            "question": question,
            "answer": f"Let's start learning step by step:\n\n{first_topic}",
            "topic": "learning_flow",
            "language": language,
            "sources": [],
            "has_context": False,
            "document_id": active_document.get("id") if active_document else None,
            "document_title": active_document.get("title") if active_document else None,
        }

    classified_topic = topic or detect_topic(question)
    active_document = get_document_by_id(document_id) if document_id is not None else None
    query_embedding = embed_query(question)

    retrieved = search_chunks(
        query_embedding,
        source_filter=source,
        topic_filter=topic,
        document_id_filter=document_id,
        limit=10,
    )
    reranked = sorted(retrieved, key=lambda item: item["score"], reverse=True)
    selected_results = _select_relevant_results(reranked, limit=6)
    context_sections = _format_context(selected_results)
    memory_lines = _memory_context_lines(limit=3)

    if not context_sections and memory_lines:
        if language.lower() == "hinglish":
            context_sections = [
                "Source: Recent chat memory\n"
                "Type: memory\n"
                "Topic: Conversation\n"
                "Chunk: 0\n"
                "Similarity: 1.000\n"
                "Content: Pichhli baat-cheet ka reference use karke answer do."
            ]
        else:
            context_sections = [
                "Source: Recent chat memory\n"
                "Type: memory\n"
                "Topic: Conversation\n"
                "Chunk: 0\n"
                "Similarity: 1.000\n"
                "Content: Use the recent conversation as the primary reference."
            ]

    if not context_sections and not memory_lines:
        answer = _fallback_answer(language)
        add_to_memory(question, answer, classified_topic)
        return {
            "question": question,
            "answer": answer,
            "topic": classified_topic,
            "language": language,
            "sources": [],
            "has_context": False,
            "document_id": document_id,
            "document_title": active_document.get("title") if active_document else None,
        }

    if intent == "summary":
        answer = answer_question(
            f"Summarize this:\n{question}",
            context_sections[:6],
            memory_lines[:3],
            language=language,
        )
    elif intent == "revision":
        answer = answer_question(
            f"Give revision points:\n{question}",
            context_sections,
            memory_lines[:3],
            language=language,
        )
    else:
        answer = answer_question(
            question,
            context_sections,
            memory_lines[:3],
            language=language,
        )

    add_to_memory(question, answer, classified_topic)
    resolved_title = (
        selected_results[0]["metadata"].get("title")
        if selected_results
        else active_document.get("title") if active_document else None
    )

    return {
        "question": question,
        "answer": answer,
        "topic": classified_topic,
        "language": language,
        "sources": [
            {
                "chunk_id": item["chunk_id"],
                "score": round(item["score"], 4),
                "metadata": item["metadata"],
            }
            for item in selected_results[:5]
        ],
        "has_context": bool(context_sections),
        "document_id": document_id,
        "document_title": resolved_title,
    }
