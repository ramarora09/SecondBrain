from __future__ import annotations

from services.embeddings import create_embeddings
from services.activity_service import record_activity
from services.graph_service import upsert_graph_from_text
from services.ocr_service import extract_text_from_image
from services.pdf_processor import extract_text
from services.topic_classifier import detect_topic
from services.vector_store import store_document
from services.youtube_ingestion import extract_transcript


def extract_text_with_ocr(file_bytes: bytes) -> tuple[str, list[str]]:
    """OCR fallback for scanned PDFs using PyMuPDF page rendering."""
    try:
        import os

        import fitz
    except Exception as exc:
        return "", [f"PDF page rendering is unavailable: {exc}"]

    full_text: list[str] = []
    warnings: list[str] = []
    try:
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
        max_pages = min(int(os.getenv("PDF_OCR_MAX_PAGES", "6")), pdf.page_count)
        max_chars = int(os.getenv("PDF_OCR_MAX_CHARS", "12000"))
        enough_chars = int(os.getenv("PDF_OCR_ENOUGH_CHARS", "6000"))
        total_chars = 0

        for index in range(max_pages):
            page = pdf[index]
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_bytes = pixmap.tobytes("png")
            text, warning = extract_text_from_image(image_bytes)
            if warning:
                warnings.append(f"Page {index + 1}: {warning}")
            if text.strip():
                page_text = f"Page {index + 1}:\n{text.strip()}"
                full_text.append(page_text)
                total_chars += len(page_text)
            if total_chars >= max_chars or total_chars >= enough_chars:
                break
    except Exception as exc:
        warnings.append(f"Scanned PDF OCR failed: {exc}")

    return "\n".join(full_text).strip(), warnings


def ingest_pdf(file_bytes: bytes, filename: str, user_id: str = "anonymous") -> dict:
    """Extract, embed, and persist a PDF with OCR fallback."""
    text = extract_text(file_bytes)
    ocr_warnings: list[str] = []

    if not text.strip():
        text, ocr_warnings = extract_text_with_ocr(file_bytes)

    if not text.strip():
        detail = " ".join(ocr_warnings[:2]).strip()
        raise ValueError(
            "No readable text found in this PDF. It appears to be scanned or image-only. "
            "Install Tesseract OCR on the backend host or configure GROQ_API_KEY for vision OCR."
            + (f" Details: {detail}" if detail else "")
        )

    chunks, embeddings = create_embeddings(text)
    if not chunks:
        raise ValueError("Could not create embeddings from the PDF.")

    topic = detect_topic(text[:2000], allow_llm_fallback=False)
    document_id = store_document(
        source_type="pdf",
        user_id=user_id,
        title=filename,
        source_ref=filename,
        topic=topic,
        content=text,
        chunks=chunks,
        embeddings=embeddings,
        metadata={"filename": filename},
    )

    upsert_graph_from_text(text[:5000], user_id=user_id)
    record_activity(
        user_id=user_id,
        event_type="document_indexed",
        entity_type="document",
        entity_id=document_id,
        metadata={"source_type": "pdf", "title": filename, "topic": topic, "chunks": len(chunks)},
    )

    return {
        "document_id": document_id,
        "title": filename,
        "topic": topic,
        "chunks_stored": len(chunks),
    }


def ingest_youtube(url: str, user_id: str = "anonymous") -> dict:
    """Extract, embed, and persist a YouTube transcript."""
    text = extract_transcript(url)
    return ingest_youtube_text(url=url, transcript=text, user_id=user_id)


def ingest_youtube_text(
    *,
    url: str,
    transcript: str,
    user_id: str = "anonymous",
    title: str | None = None,
) -> dict:
    """Embed and persist a manually supplied YouTube transcript."""
    text = " ".join((transcript or "").split()).strip()
    if len(text) < 40:
        raise ValueError("Transcript is too short to index. Paste more of the video transcript or notes.")

    chunks, embeddings = create_embeddings(text)

    if not chunks:
        raise ValueError("Could not create embeddings from the YouTube transcript.")

    topic = detect_topic(text[:2000], allow_llm_fallback=False)
    resolved_title = title or url
    document_id = store_document(
        source_type="youtube",
        user_id=user_id,
        title=resolved_title,
        source_ref=url,
        topic=topic,
        content=text,
        chunks=chunks,
        embeddings=embeddings,
        metadata={"url": url, "manual_transcript": title is not None},
    )

    upsert_graph_from_text(text[:5000], user_id=user_id)
    record_activity(
        user_id=user_id,
        event_type="document_indexed",
        entity_type="document",
        entity_id=document_id,
        metadata={"source_type": "youtube", "title": resolved_title, "topic": topic, "chunks": len(chunks)},
    )

    return {
        "document_id": document_id,
        "title": resolved_title,
        "topic": topic,
        "chunks_stored": len(chunks),
    }


def ingest_image(file_bytes: bytes, filename: str, user_id: str = "anonymous") -> dict:
    """Extract, embed, and persist image text."""
    text, warning = extract_text_from_image(file_bytes)
    if warning and not text:
        raise ValueError(warning)
    if not text.strip():
        raise ValueError("No readable text found in the uploaded image.")

    chunks, embeddings = create_embeddings(text)
    if not chunks:
        raise ValueError("Could not create embeddings from the image text.")

    topic = detect_topic(text[:2000], allow_llm_fallback=False)
    document_id = store_document(
        source_type="image",
        user_id=user_id,
        title=filename,
        source_ref=filename,
        topic=topic,
        content=text,
        chunks=chunks,
        embeddings=embeddings,
        metadata={"filename": filename},
    )

    upsert_graph_from_text(text[:5000], user_id=user_id)
    record_activity(
        user_id=user_id,
        event_type="document_indexed",
        entity_type="document",
        entity_id=document_id,
        metadata={"source_type": "image", "title": filename, "topic": topic, "chunks": len(chunks)},
    )

    return {
        "document_id": document_id,
        "title": filename,
        "topic": topic,
        "chunks_stored": len(chunks),
        "warning": warning,
        "text_preview": text[:300],
    }
