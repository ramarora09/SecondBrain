"""Analytics aggregation for the dashboard."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from shutil import which

from services.embeddings import get_embedding_backend
from services.memory_store import get_question_count, get_topic_counts
from services.study_service import get_due_flashcards
from services.vector_store import get_document_count, get_documents


def _command_available(explicit_path: str | None, command_name: str) -> bool:
    """Check whether a native OCR/PDF helper is actually runnable."""
    if explicit_path:
        try:
            if Path(explicit_path).exists():
                return True
        except OSError:
            return False
    return which(command_name) is not None


def get_system_status() -> dict:
    """Return dependency and configuration readiness for the running system."""
    dependencies = {
        "groq": importlib.util.find_spec("groq") is not None,
        "sentence_transformers": importlib.util.find_spec("sentence_transformers") is not None,
        "pypdf": importlib.util.find_spec("pypdf") is not None,
        "youtube_transcript_api": importlib.util.find_spec("youtube_transcript_api") is not None,
        "pytesseract": importlib.util.find_spec("pytesseract") is not None,
        "pdf2image": importlib.util.find_spec("pdf2image") is not None,
    }

    config = {
        "groq_api_key_configured": bool(os.getenv("GROQ_API_KEY")),
        "tesseract_cmd_configured": bool(os.getenv("TESSERACT_CMD")),
        "tesseract_available": _command_available(os.getenv("TESSERACT_CMD"), "tesseract"),
        "poppler_available": _command_available(os.getenv("POPPLER_PATH"), "pdfinfo"),
    }

    embedding_backend = get_embedding_backend()
    embedding_model_ready = False
    if embedding_backend == "transformer" and dependencies["sentence_transformers"]:
        try:
            from services.embeddings import get_model
            embedding_model_ready = get_model() is not None
        except Exception:
            embedding_model_ready = False
    warnings: list[str] = []
    if not dependencies["groq"] or not config["groq_api_key_configured"]:
        warnings.append("LLM responses are running in fallback mode until Groq and GROQ_API_KEY are configured.")
    if embedding_backend == "transformer" and (not dependencies["sentence_transformers"] or not embedding_model_ready):
        warnings.append("Transformer embeddings are unavailable, so retrieval may fall back to hash embeddings.")
    if embedding_backend == "hash":
        warnings.append("Fast hash embeddings are enabled for quicker uploads and lower startup cost.")
    if not dependencies["youtube_transcript_api"]:
        warnings.append("YouTube ingestion needs youtube-transcript-api installed.")
    if not dependencies["pypdf"]:
        warnings.append("PDF ingestion needs pypdf installed.")
    if not dependencies["pytesseract"]:
        warnings.append("Image OCR needs pytesseract installed.")
    if not dependencies["pdf2image"]:
        warnings.append("Scanned PDF OCR needs pdf2image installed.")
    if dependencies["pdf2image"] and not config["poppler_available"]:
        warnings.append("Scanned PDF OCR still needs Poppler installed and pdfinfo available on PATH.")
    if dependencies["pytesseract"] and not config["tesseract_available"]:
        warnings.append("Image OCR needs a working Tesseract binary on the deployment host.")

    llm_ready = dependencies["groq"] and config["groq_api_key_configured"]
    ingestion_ready = dependencies["pypdf"] and dependencies["youtube_transcript_api"]
    retrieval_mode = "sentence-transformers" if embedding_backend == "transformer" and embedding_model_ready else "hash"

    return {
        "ready": llm_ready and ingestion_ready,
        "llm_ready": llm_ready,
        "ingestion_ready": ingestion_ready,
        "embedding_model_ready": embedding_model_ready,
        "embedding_backend": embedding_backend,
        "retrieval_mode": retrieval_mode,
        "dependencies": dependencies,
        "config": config,
        "warnings": warnings,
    }


def get_analytics_summary(user_id: str = "anonymous") -> dict:
    """Return analytics data used by the API and dashboard."""
    topics = get_topic_counts(user_id=user_id)
    documents = get_documents(limit=10, user_id=user_id)

    return {
        "total_questions": get_question_count(user_id=user_id),
        "topics": topics,
        "documents_uploaded": get_document_count(user_id=user_id),
        "recent_documents": documents,
        "due_flashcards": len(get_due_flashcards(user_id=user_id)),
        "system_status": get_system_status(),
    }
