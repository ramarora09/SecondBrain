"""Production-style retrieval augmented generation flow with intelligence layer."""

from __future__ import annotations

import re

from services.embeddings import embed_query
from services.llm_service import answer_question, complete_text
from services.memory_store import add_to_memory, get_memory, get_next_topic, start_topic
from services.topic_classifier import detect_topic
from services.vector_store import (
    get_document_by_id,
    get_document_chunks,
    get_document_content,
    get_latest_document,
    search_chunks,
)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "that", "the",
    "this", "to", "was", "what", "when", "where", "which", "who", "why",
    "with", "you", "your", "explain", "tell", "give", "define",
}


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


def _keywords(text: str) -> set[str]:
    """Extract meaningful query/document words for a simple relevance guard."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_+#-]{2,}", text.lower())
    return {word.strip("-_") for word in words if word not in STOPWORDS}


def _lexical_overlap(question: str, chunk_text: str) -> float:
    """Return how much a chunk literally overlaps with the user's question."""
    question_terms = _keywords(question)
    if not question_terms:
        return 0.0

    chunk_terms = _keywords(chunk_text)
    if not chunk_terms:
        return 0.0

    return len(question_terms & chunk_terms) / len(question_terms)


def _rerank_with_lexical_signal(question: str, results: list[dict]) -> list[dict]:
    """Combine vector similarity with keyword overlap to avoid random off-topic chunks."""
    reranked: list[dict] = []
    for item in results:
        lexical_score = _lexical_overlap(question, item.get("text", ""))
        combined_score = (float(item.get("score", 0.0)) * 0.65) + (lexical_score * 0.35)
        reranked.append({**item, "lexical_score": lexical_score, "combined_score": combined_score})

    reranked.sort(key=lambda item: item["combined_score"], reverse=True)
    return reranked


def _select_relevant_results(
    results: list[dict],
    *,
    question: str,
    limit: int = 6,
    require_source_match: bool = False,
) -> list[dict]:
    """Keep only the strongest retrieval matches for prompting."""
    if not results:
        return []

    generic_source_request = any(
        phrase in question.lower()
        for phrase in ["summarize", "summary", "revise", "revision", "start", "teach", "from pdf", "from the pdf"]
    )
    if require_source_match and not generic_source_request:
        filtered = [
            item
            for item in results
            if item.get("lexical_score", 0.0) >= 0.18 or item.get("score", 0.0) >= 0.42
        ]
        return filtered[:limit]

    filtered = [
        item
        for item in results
        if item.get("score", 0.0) >= 0.12 or item.get("lexical_score", 0.0) >= 0.18
    ]
    if not filtered:
        filtered = results[:2]

    return filtered[:limit]


def detect_intent(question: str) -> str:
    """Infer the interaction intent from the question text."""
    q = question.lower()

    if "next" in q:
        return "next"
    if any(phrase in q for phrase in ["continue", "go on", "carry on", "send me more", "tell me next", "move ahead"]):
        return "next"
    if "teach" in q or "start" in q:
        return "teaching"
    if "summarize" in q:
        return "summary"
    if "revise" in q:
        return "revision"
    return "qa"


def _clean_topic_lines(raw_text: str) -> list[str]:
    numbered_topics: list[str] = []
    short_topics: list[str] = []
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue

        numbered_match = re.match(r"^\d+[\).\-\s]+(.+)$", cleaned)
        if numbered_match:
            topic = numbered_match.group(1).strip()
            if topic:
                numbered_topics.append(topic)
            continue

        bullet_match = re.match(r"^[-*]\s+(.+)$", cleaned)
        if bullet_match:
            topic = bullet_match.group(1).strip()
            if topic and len(topic.split()) <= 12:
                short_topics.append(topic)
            continue

        if len(cleaned.split()) <= 12 and not cleaned.endswith(":"):
            short_topics.append(cleaned)

    topics = numbered_topics or short_topics
    filtered: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        lowered = topic.lower()
        if lowered.startswith("here's") or lowered.startswith("here is"):
            continue
        if "study flow" in lowered and len(topic.split()) > 6:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        filtered.append(topic)

    return filtered


def _fallback_topics_from_content(content: str, title: str | None = None) -> list[str]:
    topic_candidates = _extract_readable_points(content, limit=6)
    if topic_candidates:
        return topic_candidates[:5]

    if title:
        return [
            f"Introduction to {title}",
            "Core concepts",
            "Important examples",
            "Applications and use cases",
            "Revision summary",
        ]

    return ["Introduction to the topic", "Core ideas", "Important examples", "Applications", "Revision points"]


def _fallback_topics_from_topic(topic: str | None, title: str | None = None) -> list[str]:
    normalized = (topic or "").lower()
    if normalized == "ai/ml":
        return [
            f"Introduction to {title}" if title else "Introduction to Machine Learning",
            "Supervised learning",
            "Unsupervised learning",
            "Reinforcement learning",
            "Model evaluation and revision",
        ]
    if normalized == "os":
        return [
            f"Introduction to {title}" if title else "Introduction to Operating Systems",
            "Processes and threads",
            "Scheduling and synchronization",
            "Memory management",
            "Deadlocks and revision",
        ]
    if normalized == "dbms":
        return [
            f"Introduction to {title}" if title else "Introduction to DBMS",
            "Relational model",
            "SQL and queries",
            "Normalization and transactions",
            "Indexes and revision",
        ]
    if normalized == "dsa":
        return [
            f"Introduction to {title}" if title else "Introduction to DSA",
            "Core data structures",
            "Searching and sorting",
            "Graphs and dynamic programming",
            "Problem-solving revision",
        ]
    if normalized in {"backend", "frontend", "devops"}:
        return [
            f"Introduction to {title}" if title else f"Introduction to {topic}",
            "Core concepts",
            "Important workflows",
            "Examples and applications",
            "Revision summary",
        ]
    return _fallback_topics_from_content("", title)


def _readability_score(text: str) -> float:
    cleaned = text.strip()
    if not cleaned:
        return 0.0

    allowed = sum(1 for char in cleaned if char.isalnum() or char in " .,:%-()")
    return allowed / max(len(cleaned), 1)


def _is_readable_line(text: str) -> bool:
    cleaned = " ".join(text.split()).strip()
    if len(cleaned) < 12 or len(cleaned) > 120:
        return False
    if sum(1 for char in cleaned if char.isalpha()) < 8:
        return False
    if _readability_score(cleaned) < 0.82:
        return False
    return True


def _extract_readable_points(content: str, limit: int = 6) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    for piece in re.split(r"[.\n]+", content):
        cleaned = " ".join(piece.split()).strip(" -:;")
        if not _is_readable_line(cleaned):
            continue

        normalized = cleaned.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(cleaned)
        if len(candidates) >= limit:
            break

    return candidates


def _document_text_for_teaching(document_id: int | None, user_id: str) -> tuple[str | None, str | None]:
    """Resolve the best available document text for topic generation."""
    if document_id is None:
        return None, None

    document = get_document_content(document_id, user_id=user_id)
    if document and document.get("content"):
        content = str(document["content"]).strip()
        if content:
            return document.get("title"), content

    chunks = get_document_chunks(document_id, limit=24, user_id=user_id)
    if not chunks:
        return (document or {}).get("title"), None

    combined = "\n".join(chunk["chunk_text"] for chunk in chunks if chunk.get("chunk_text"))
    return (document or {}).get("title"), combined.strip() or None


def _document_quality_message(title: str | None, language: str) -> str:
    label = title or "this source"
    if language.lower() == "hinglish":
        return (
            f"Mujhe {label} mila, lekin extracted text quality weak lag rahi hai. "
            "PDF scan ya OCR output clear nahi hai, isliye topics aur explanations reliable nahi ban rahe. "
            "Clear digital PDF upload karo ya better scan use karo."
        )
    return (
        f"I found {label}, but the extracted text quality is too weak for reliable topics and explanations. "
        "The PDF scan or OCR output is noisy. Upload a clearer digital PDF or a better scan."
    )


def generate_topics(
    question: str,
    *,
    document_title: str | None = None,
    document_content: str | None = None,
) -> list[str]:
    """Break an uploaded document or topic into an ordered study flow."""
    if document_content:
        prompt = f"""
Create a step-by-step study flow from this uploaded source.

User request:
{question}

Document title:
{document_title or "Uploaded source"}

Document content excerpt:
{document_content[:4000]}

Rules:
- Return 4 to 7 short learning topics
- Start from fundamentals
- Move toward deeper concepts
- Keep each topic on its own numbered line
- Use the uploaded source, not generic filler
"""
        try:
            response = complete_text(prompt=prompt)
            topics = _clean_topic_lines(response)
            if topics:
                return topics
        except Exception:
            return _fallback_topics_from_content(document_content, document_title)

        return _fallback_topics_from_content(document_content, document_title)

    prompt = f"""
Break this topic into step-by-step learning topics.

Topic:
{question}

Return only a numbered list.
"""
    try:
        response = complete_text(prompt=prompt)
        topics = _clean_topic_lines(response)
        if topics:
            return topics
    except Exception:
        pass

    return ["Introduction to the topic", "Core concepts", "Important examples", "Revision summary"]


def _memory_context_lines(limit: int = 3, user_id: str = "anonymous") -> list[str]:
    return [f"Q: {item['question']}\nA: {item['answer']}" for item in get_memory(limit=limit, user_id=user_id)]


def _fallback_answer(language: str) -> str:
    if language.lower() == "hinglish":
        return (
            "Mujhe abhi relevant context nahi mila. Pehle PDF, image, ya YouTube source upload karo, "
            "ya thoda specific question poochho."
        )
    return "I could not find relevant context yet. Upload a PDF, image, or YouTube source, or ask a more specific question."


def _outside_uploaded_source_answer(question: str, document_title: str | None, language: str) -> str:
    """Tell the user clearly when their question is outside the active upload."""
    title = document_title or "the active uploaded source"
    if language.lower() == "hinglish":
        return (
            "Direct Answer:\n"
            f"Is question ka clear answer mujhe {title} ke indexed text me nahi mila.\n\n"
            "Main Explanation:\n"
            "Main abhi uploaded notes se grounded answer dene ki koshish kar raha hoon, random general chatbot answer nahi. "
            "Agar aap general answer chahte ho, prompt me likho: `answer generally`.\n\n"
            "Key Points:\n"
            f"- Active source: {title}\n"
            f"- Question: {question}\n"
            "- Matching source chunk strong nahi mila\n\n"
            "Mini Diagram:\n"
            "Question -> Search uploaded notes -> No strong match -> Ask source-related question or enable general answer\n\n"
            "Short Summary:\n"
            "PDF se related question poochho, ya general mode explicitly mention karo."
        )

    return (
        "Direct Answer:\n"
        f"I could not find a reliable answer to this question inside {title}.\n\n"
        "Main Explanation:\n"
        "I am prioritizing your uploaded notes instead of behaving like a generic chatbot. "
        "If you want a general answer, ask with: `answer generally`.\n\n"
        "Key Points:\n"
        f"- Active source: {title}\n"
        f"- Question: {question}\n"
        "- No strongly matching source chunk was found\n\n"
        "Mini Diagram:\n"
        "Question -> Search uploaded notes -> No strong match -> Ask source-related question or request general answer\n\n"
        "Short Summary:\n"
        "Ask something related to the uploaded PDF, or explicitly request a general explanation."
    )


def _clarify_brief_prompt(question: str, language: str, document_title: str | None = None) -> str | None:
    normalized = " ".join(question.lower().split())
    if normalized not in {"send", "send me", "tell me", "give", "give me"}:
        return None

    if language.lower() == "hinglish":
        if document_title:
            return (
                f"Mujhe {document_title} ke liye thoda aur specific prompt chahiye. "
                "Try `next`, `summarize this topic`, `explain with diagram`, ya `give revision notes`."
            )
        return "Thoda aur specific prompt do. Try `next`, `summarize this`, ya `explain with diagram`."

    if document_title:
        return (
            f"I need a more specific request for {document_title}. "
            "Try `next`, `summarize this topic`, `explain with diagram`, or `give revision notes`."
        )
    return "I need a more specific request. Try `next`, `summarize this`, or `explain with diagram`."


def _is_generic_start_prompt(question: str) -> bool:
    return question.lower().strip() in {
        "start",
        "start from first topic",
        "start from first topic of the pdf",
        "explain every topic from start",
        "explain every topic from the start",
    }


def query_knowledge_base(
    question: str,
    source: str = "all",
    topic: str | None = None,
    language: str = "english",
    document_id: int | None = None,
    user_id: str = "anonymous",
) -> dict:
    """Answer a question using retrieved knowledge, memory, and learning flow."""
    question = question.strip()
    if not question:
        raise ValueError("Question cannot be empty")

    intent = detect_intent(question)
    active_document = get_document_by_id(document_id, user_id=user_id) if document_id is not None else None

    clarification = _clarify_brief_prompt(
        question,
        language,
        active_document.get("title") if active_document else None,
    )
    if clarification:
        return {
            "question": question,
            "answer": clarification,
            "topic": "clarification",
            "language": language,
            "sources": [],
            "has_context": False,
            "document_id": document_id,
            "document_title": active_document.get("title") if active_document else None,
        }

    if intent == "next":
        next_topic = get_next_topic(user_id)
        if next_topic is None and document_id is not None:
            title, document_text = _document_text_for_teaching(document_id, user_id=user_id)
            if document_text:
                active_document = get_document_by_id(document_id, user_id=user_id)
                readable_points = _extract_readable_points(document_text, limit=5)
                if not readable_points:
                    readable_points = _fallback_topics_from_topic(
                        active_document.get("topic") if active_document else None,
                        active_document.get("title") if active_document else None,
                    )
                topics = generate_topics(
                    "Continue with the uploaded document",
                    document_title=title,
                    document_content=document_text,
                )
                if not topics or not _extract_readable_points("\n".join(topics), limit=1):
                    topics = readable_points
                start_topic(
                    user_id,
                    topics,
                    document_id=document_id,
                    document_title=title,
                    start_index=0,
                )
                next_topic = get_next_topic(user_id)

        if next_topic is None and document_id is not None:
            active_document = get_document_by_id(document_id, user_id=user_id)
            unreadable_answer = _document_quality_message(
                active_document.get("title") if active_document else None,
                language,
            )
            return {
                "question": question,
                "answer": unreadable_answer,
                "topic": "learning_flow",
                "language": language,
                "sources": [],
                "has_context": False,
                "document_id": document_id,
                "document_title": active_document.get("title") if active_document else None,
            }

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
        active_document = active_document if active_document is not None else get_latest_document(user_id=user_id)
        title, document_text = _document_text_for_teaching(
            active_document.get("id") if active_document else None,
            user_id=user_id,
        )

        if active_document is None and any(keyword in question.lower() for keyword in ["pdf", "document", "file", "upload"]):
            answer = (
                "Mujhe active uploaded source nahi mila. Pehle PDF, image, ya YouTube source select ya upload karo."
                if language.lower() == "hinglish"
                else "I could not find an active uploaded source. Upload or select a PDF, image, or YouTube source first."
            )
            return {
                "question": question,
                "answer": answer,
                "topic": "learning_flow",
                "language": language,
                "sources": [],
                "has_context": False,
                "document_id": None,
                "document_title": None,
            }

        if active_document is not None and not document_text:
            topics = _fallback_topics_from_topic(active_document.get("topic"), active_document.get("title"))
        else:
            readable_points = _extract_readable_points(document_text or "", limit=5)
            if active_document is not None and (
                not readable_points or (
                    _is_generic_start_prompt(question)
                    and (
                        len(readable_points) < 3
                        or any(len(point.split()) <= 2 for point in readable_points[:2])
                    )
                )
            ):
                topics = _fallback_topics_from_topic(active_document.get("topic"), active_document.get("title"))
            else:
                topics = None

        teaching_prompt = (
            f"Create a study flow for {active_document.get('title')}"
            if active_document and _is_generic_start_prompt(question)
            else question
        )

        if topics is None:
            topics = generate_topics(
                teaching_prompt,
                document_title=title or active_document.get("title") if active_document else None,
                document_content=document_text,
            )
            if not topics or not _extract_readable_points("\n".join(topics), limit=1):
                topics = readable_points or _fallback_topics_from_topic(
                    active_document.get("topic") if active_document else None,
                    active_document.get("title") if active_document else None,
                )
        start_topic(
            user_id,
            topics,
            document_id=active_document.get("id") if active_document else None,
            document_title=active_document.get("title") if active_document else None,
            start_index=1 if topics else 0,
        )
        first_topic = topics[0] if topics else question
        return {
            "question": question,
            "answer": (
                f"Let's start learning step by step from {active_document.get('title')}:\n\n{first_topic}"
                if active_document
                else f"Let's start learning step by step:\n\n{first_topic}"
            ),
            "topic": "learning_flow",
            "language": language,
            "sources": [],
            "has_context": False,
            "document_id": active_document.get("id") if active_document else None,
            "document_title": active_document.get("title") if active_document else None,
        }

    classified_topic = topic or detect_topic(question)
    query_embedding = embed_query(question)

    retrieved = search_chunks(
        query_embedding,
        source_filter=source,
        topic_filter=topic,
        document_id_filter=document_id,
        user_id=user_id,
        limit=10,
    )
    reranked = sorted(retrieved, key=lambda item: item["score"], reverse=True)
    reranked = _rerank_with_lexical_signal(question, reranked)
    selected_results = _select_relevant_results(
        reranked,
        question=question,
        limit=6,
        require_source_match=active_document is not None,
    )
    context_sections = _format_context(selected_results)
    memory_lines = _memory_context_lines(limit=3, user_id=user_id)

    if active_document is not None and not selected_results and intent == "qa":
        answer = _outside_uploaded_source_answer(question, active_document.get("title"), language)
        add_to_memory(question, answer, classified_topic, user_id=user_id)
        return {
            "question": question,
            "answer": answer,
            "topic": "outside_source",
            "language": language,
            "sources": [],
            "has_context": False,
            "document_id": document_id,
            "document_title": active_document.get("title"),
        }

    if not context_sections and memory_lines and active_document is None:
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
        add_to_memory(question, answer, classified_topic, user_id=user_id)
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

    add_to_memory(question, answer, classified_topic, user_id=user_id)
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
