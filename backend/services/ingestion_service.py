from __future__ import annotations

import os

from services.embeddings import create_embeddings
from services.activity_service import record_activity
from services.graph_service import upsert_graph_from_text
from services.ocr_service import extract_text_from_image
from services.pdf_processor import extract_text
from services.topic_classifier import detect_topic
from services.vector_store import store_document
from services.youtube_ingestion import extract_transcript


def extract_text_with_ocr(file_bytes: bytes) -> str:
    """Optional OCR fallback for scanned PDFs."""
    try:
        from io import BytesIO
        from pdf2image import convert_from_bytes
    except Exception:
        return ""

    full_text: list[str] = []
    try:
        poppler_path = os.getenv("POPPLER_PATH") or None
        max_pages = int(os.getenv("PDF_OCR_MAX_PAGES", "8"))
        max_chars = int(os.getenv("PDF_OCR_MAX_CHARS", "50000"))
        images = convert_from_bytes(
            file_bytes,
            poppler_path=poppler_path,
            first_page=1,
            last_page=max_pages,
        )
        for image in images:
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            text, warning = extract_text_from_image(buffer.getvalue())
            if warning and not text:
                continue
            if text.strip():
                full_text.append(text.strip())
            if sum(len(part) for part in full_text) >= max_chars:
                break
    except Exception:
        return ""

    return "\n".join(full_text).strip()


def ingest_pdf(file_bytes: bytes, filename: str, user_id: str = "anonymous") -> dict:
    """Extract, embed, and persist a PDF with OCR fallback."""
    text = extract_text(file_bytes)

    if not text.strip():
        text = extract_text_with_ocr(file_bytes)

    if not text.strip():
        raise ValueError(
            "No readable text found in this PDF. If it is scanned, install Poppler (pdfinfo on PATH), pdf2image, and Tesseract OCR."
        )

    chunks, embeddings = create_embeddings(text)
    if not chunks:
        raise ValueError("Could not create embeddings from the PDF.")

    topic = detect_topic(text[:2000])
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
    chunks, embeddings = create_embeddings(text)

    if not chunks:
        raise ValueError("Could not create embeddings from the YouTube transcript.")

    topic = detect_topic(text[:2000])
    document_id = store_document(
        source_type="youtube",
        user_id=user_id,
        title=url,
        source_ref=url,
        topic=topic,
        content=text,
        chunks=chunks,
        embeddings=embeddings,
        metadata={"url": url},
    )

    upsert_graph_from_text(text[:5000], user_id=user_id)
    record_activity(
        user_id=user_id,
        event_type="document_indexed",
        entity_type="document",
        entity_id=document_id,
        metadata={"source_type": "youtube", "title": url, "topic": topic, "chunks": len(chunks)},
    )

    return {
        "document_id": document_id,
        "title": url,
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

    topic = detect_topic(text[:2000])
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
