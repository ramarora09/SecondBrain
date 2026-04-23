"""Embedding and chunking helpers."""

from __future__ import annotations

import hashlib
import importlib
import os
from typing import Any

model = None


def get_embedding_backend() -> str:
    """Return the configured embedding backend."""
    backend = (os.getenv("EMBEDDING_BACKEND") or "hash").strip().lower()
    if backend in {"transformer", "hash"}:
        return backend
    return "hash"


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _hash_embed(text: str, dimensions: int = 384) -> list[float]:
    """Create a deterministic lightweight embedding when transformer models are unavailable."""
    vector = [0.0] * dimensions
    tokens = [token for token in text.lower().split() if token]

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + (digest[5] / 255.0)
        vector[index] += sign * weight

    return _normalize_vector(vector)


def _chunking_profile(text_length: int) -> tuple[int, int]:
    """Choose chunking settings based on document size for faster ingestion."""
    if text_length > 400_000:
        return 2400, 250
    if text_length > 180_000:
        return 1800, 220
    if text_length > 60_000:
        return 1400, 180
    return 900, 140


def get_model() -> Any:
    """Lazily load the sentence transformer model."""
    global model

    if get_embedding_backend() != "transformer":
        return None

    if model is None:
        try:
            sentence_transformers = importlib.import_module("sentence_transformers")
            SentenceTransformer = sentence_transformers.SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
        except Exception:
            return None

    return model


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """Split text into overlapping chunks while preserving sentence boundaries."""
    cleaned_text = " ".join(text.split())
    if not cleaned_text:
        return []

    if chunk_size is None or overlap is None:
        chunk_size, overlap = _chunking_profile(len(cleaned_text))

    chunks: list[str] = []
    start = 0
    step = max(chunk_size - overlap, 1)

    while start < len(cleaned_text):
        end = min(start + chunk_size, len(cleaned_text))
        if end < len(cleaned_text):
            sentence_break = cleaned_text.rfind(". ", start, end)
            newline_break = cleaned_text.rfind("\n", start, end)
            split_at = max(sentence_break, newline_break)
            if split_at > start + 100:
                end = split_at + 1

        chunk = cleaned_text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(cleaned_text):
            break
        start += step

    return chunks


def create_embeddings(text: str) -> tuple[list[str], list[list[float]]]:
    """Create semantic chunks and embeddings for a text payload."""
    chunks = chunk_text(text)
    if not chunks:
        return [], []

    embedding_model = get_model()
    if embedding_model is None:
        embeddings = [_hash_embed(chunk) for chunk in chunks]
    else:
        embeddings = embedding_model.encode(chunks, convert_to_numpy=True).tolist()
    return chunks, embeddings


def embed_query(question: str) -> list[float]:
    """Create an embedding for a single query string."""
    embedding_model = get_model()
    if embedding_model is None:
        return _hash_embed(question)
    return embedding_model.encode([question], convert_to_numpy=True)[0].tolist()
