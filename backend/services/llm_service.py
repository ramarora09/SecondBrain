"""Advanced LLM helpers with intelligent behavior."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv

try:
    from groq import Groq
except Exception:
    Groq = None

load_dotenv()

_client = None


# 🔥 CLIENT INIT
def get_client() -> Any | None:
    global _client

    if _client is not None:
        return _client

    if Groq is None:
        return None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    _client = Groq(api_key=api_key)
    return _client


# 🔥 CORE COMPLETION
def complete_text(
    *,
    prompt: str,
    system_prompt: str | None = None,
    model: str = "llama-3.1-8b-instant",
    temperature: float = 0.3,
) -> str:
    client = get_client()
    if client is None:
        raise RuntimeError("GROQ_API_KEY is not configured")

    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )

    return response.choices[0].message.content.strip()


# 🔥 SMART LANGUAGE STYLE
def _language_instruction(language: str) -> str:
    normalized = (language or "english").strip().lower()

    if normalized == "hinglish":
        return (
            "Reply in simple Hinglish. Easy Hindi + English mix use karo. "
            "Friendly tone rakho, examples do, aur easy samjhao."
        )

    return "Reply in clear, simple English with proper explanation."


def _structure_instruction(question: str, language: str) -> str:
    normalized_question = (question or "").lower()
    calculation_keywords = [
        "calculate",
        "solve",
        "find",
        "equation",
        "probability",
        "derivative",
        "integral",
        "matrix",
        "loss",
        "accuracy",
        "mean",
        "variance",
        "formula",
        "proof",
    ]
    is_calculation = any(keyword in normalized_question for keyword in calculation_keywords)

    if language.lower() == "hinglish":
        if is_calculation:
            return (
                "Answer ko strict structured format me do:\n"
                "Direct Answer:\n"
                "Formula / Concept:\n"
                "Step-by-Step Solution:\n"
                "Mini Diagram:\n"
                "Final Result:\n"
                "Short Intuition:\n"
                "Har step alag line me rakho. Mini Diagram me arrow flow use karo jaise A -> B -> C. Calculation skip mat karo."
            )
        return (
            "Answer ko structured format me do:\n"
            "Direct Answer:\n"
            "Main Explanation:\n"
            "Key Points:\n"
            "Example:\n"
            "Mini Diagram:\n"
            "Short Summary:\n"
            "Complex text ko short sections me tod do. Mini Diagram me 1-3 short lines ya arrow flow use karo."
        )

    if is_calculation:
        return (
            "Use this structured format:\n"
            "Direct Answer:\n"
            "Formula / Concept:\n"
            "Step-by-Step Solution:\n"
            "Mini Diagram:\n"
            "Final Result:\n"
            "Short Intuition:\n"
            "Show each important calculation step clearly. Use the Mini Diagram section for a short arrow flow such as Input -> Process -> Output."
        )

    return (
        "Use this structured format:\n"
        "Direct Answer:\n"
        "Main Explanation:\n"
        "Key Points:\n"
        "Example:\n"
        "Mini Diagram:\n"
        "Short Summary:\n"
        "Keep each section concise and readable. In Mini Diagram, show a compact text diagram with arrows or 2-4 labeled steps."
    )


def _build_local_answer(question: str, context_sections: list[str], language: str) -> str:
    """Create a useful fallback answer without an LLM."""
    def is_readable_snippet(text: str) -> bool:
        cleaned = " ".join(text.split()).strip()
        if len(cleaned) < 20:
            return False
        words = cleaned.split()
        if len(words) < 5:
            return False
        letters = sum(1 for char in cleaned if char.isalpha())
        allowed = sum(1 for char in cleaned if char.isalnum() or char in " .,:%-()")
        alphabetic_words = sum(1 for word in words if sum(1 for char in word if char.isalpha()) >= max(2, len(word) // 2))
        uppercase_words = sum(1 for word in words if word.isupper() and len(word) > 2)
        average_word_length = sum(len(word.strip(".,:%-()")) for word in words) / max(len(words), 1)
        symbol_heavy_words = sum(1 for word in words if sum(1 for char in word if not char.isalnum()) > 2)
        return (
            letters >= 18
            and (allowed / max(len(cleaned), 1)) >= 0.9
            and alphabetic_words >= max(4, len(words) // 2)
            and uppercase_words <= 1
            and 3.0 <= average_word_length <= 9.5
            and symbol_heavy_words <= 1
        )

    snippets = [
        section.split("Content:", 1)[-1].strip()
        for section in context_sections[:4]
        if section.strip()
    ]
    readable_snippets = [snippet for snippet in snippets if is_readable_snippet(snippet)]

    quality_sensitive_question = any(
        phrase in (question or "").lower()
        for phrase in ["summarize", "revision", "diagram", "explain", "notes"]
    )

    if not readable_snippets or (quality_sensitive_question and len(readable_snippets) < 2):
        if language.lower() == "hinglish":
            return (
                "Direct Answer:\n"
                "Source text quality weak lag rahi hai, isliye reliable explanation nikalna mushkil hai.\n\n"
                "Key Points:\n"
                "- Uploaded source me OCR ya extracted text noisy hai\n"
                "- Better digital PDF ya clearer scan se answer quality improve hogi\n\n"
                "Mini Diagram:\n"
                "Uploaded file -> Weak text extraction -> Weak explanation quality\n\n"
                "Short Summary:\n"
                "Clear source upload karo, phir main isko proper notes aur diagrams me tod dunga."
            )

        return (
            "Direct Answer:\n"
            "The source text quality is too noisy for a reliable grounded explanation.\n\n"
            "Key Points:\n"
            "- The uploaded source contains weak OCR or messy extracted text\n"
            "- A clearer digital PDF or better scan will improve the answer quality\n\n"
            "Mini Diagram:\n"
            "Uploaded file -> Weak text extraction -> Weak explanation quality\n\n"
            "Short Summary:\n"
            "Upload a cleaner source and I can turn it into proper notes, explanations, and diagrams."
        )

    summary = "\n".join(f"- {snippet[:220]}" for snippet in readable_snippets[:3])

    if language.lower() == "hinglish":
        return (
            "Direct Answer:\n"
            "Model abhi respond nahi kar raha, lekin retrieved knowledge ke basis par yeh best structured answer hai.\n\n"
            "Key Points:\n"
            f"{summary}\n\n"
            "Question Focus:\n"
            f"{question}\n\n"
            "Mini Diagram:\n"
            "Question -> Retrieved context -> Key idea\n\n"
            "Short Summary:\n"
            "Agar chaho to main isi topic ko aur simple steps me bhi tod sakta hoon."
        )

    return (
        "Direct Answer:\n"
        "The model is unavailable right now, but here is the best grounded answer from retrieved knowledge.\n\n"
        "Key Points:\n"
        f"{summary}\n\n"
        "Question Focus:\n"
        f"{question}\n\n"
        "Mini Diagram:\n"
        "Question -> Retrieved context -> Key idea\n\n"
        "Short Summary:\n"
        "Ask a narrower follow-up if you want a cleaner step-by-step explanation."
    )


# 🔥 MAIN INTELLIGENT ANSWER FUNCTION
def answer_question(
    question: str,
    context_sections: list[str],
    memory_lines: list[str],
    language: str = "english",
) -> str:

    context_block = "\n\n".join(section for section in context_sections if section.strip())
    memory_block = "\n".join(memory_lines[:3])
    language_instruction = _language_instruction(language)
    structure_instruction = _structure_instruction(question, language)

    # 🔥 FALLBACK (NO DATA)
    if not context_block and not memory_block:
        if language.lower() == "hinglish":
            return (
                "Mujhe abhi relevant data nahi mila. Pehle PDF ya YouTube upload karo ya specific question poochho."
            )
        return (
            "I couldn't find relevant knowledge yet. Please upload content or ask a more specific question."
        )

    # 🔥 SUPER PROMPT (INTELLIGENCE CORE)
    system_prompt = """
You are an advanced AI tutor and personal knowledge assistant.

Your behavior:
- Understand user's intent deeply
- Adapt explanation level (beginner → simple, advanced → detailed)
- Detect confusion and simplify automatically
- Continue learning flow when user says "next"
- Avoid robotic answers

Teaching style:
- Step-by-step explanation
- Use real-world examples
- Break complex topics into simple parts
- Keep answers engaging and natural
- Add a compact text-only diagram when it improves understanding
"""

    prompt = f"""
Follow the instructions carefully.

Response style:
{language_instruction}

Response structure:
{structure_instruction}

Recent conversation:
{memory_block or "No previous conversation."}

Knowledge context:
{context_block or "No matching context."}

User question:
{question}

Answer:
"""

    try:
        return complete_text(prompt=prompt, system_prompt=system_prompt)

    except Exception:
        if context_block:
            return _build_local_answer(question, context_sections, language)

        if language.lower() == "hinglish":
            return "System temporarily unavailable hai, thoda baad try karo."
        return "System is temporarily unavailable. Please try again."


# 🔥 TOPIC CLASSIFICATION
def classify_topic_with_llm(question: str, available_topics: list[str] | None = None) -> str | None:
    topics_line = ", ".join(available_topics or [])

    prompt = f"""
Classify the topic of this question in one short label.

Topics: {topics_line or 'AI, DSA, DBMS, OS, Backend, Frontend'}

Question:
{question}

Topic:
"""

    try:
        label = complete_text(prompt=prompt, temperature=0.0)
        return label.strip().split("\n")[0][:40]
    except Exception:
        return None


# 🔥 FLASHCARDS GENERATION
def generate_flashcards_with_llm(topic: str, text: str, limit: int) -> list[dict[str, str]]:
    prompt = f"""
Generate {limit} flashcards in JSON format.

Topic: {topic}

Each flashcard:
- question
- answer

Content:
{text[:4000]}
"""

    try:
        raw = complete_text(prompt=prompt, temperature=0.3)
        cards = json.loads(raw)

        if isinstance(cards, list):
            return [
                {
                    "question": str(card.get("question", "")).strip(),
                    "answer": str(card.get("answer", "")).strip(),
                }
                for card in cards
                if card.get("question") and card.get("answer")
            ][:limit]

    except Exception:
        return []

    return []


# 🔥 STUDY RECOMMENDATION
def recommend_study_focus(summary: dict) -> str:
    prompt = f"""
Give a smart study recommendation.

Topics: {summary.get("topics")}
Weak areas: {summary.get("weak_topics")}
Due flashcards: {summary.get("due_flashcards")}

Keep it short and actionable.
"""

    try:
        return complete_text(prompt=prompt, temperature=0.3)
    except Exception:
        return "Focus on weak topics and revise flashcards."
