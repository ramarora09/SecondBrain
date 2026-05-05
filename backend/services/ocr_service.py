"""OCR extraction with Tesseract first and Groq vision fallback."""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
from shutil import which

from PIL import Image

from services.llm_service import get_client

try:
    import pytesseract
except Exception:
    pytesseract = None

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def _prepare_image_for_vision(file_bytes: bytes) -> tuple[bytes, str]:
    """Resize and compress images before sending them to vision OCR."""
    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    except Exception:
        return file_bytes, "image/png"

    max_side = 1600
    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=72, optimize=True)
    return buffer.getvalue(), "image/jpeg"


def extract_text_with_groq_vision(file_bytes: bytes, mime_type: str = "image/png") -> tuple[str, str | None]:
    """Extract text from an image using the already configured Groq client."""
    client = get_client()
    if client is None:
        return "", "Groq API key is not configured for vision OCR."

    try:
        prepared_bytes, prepared_mime_type = _prepare_image_for_vision(file_bytes)
        encoded = base64.b64encode(prepared_bytes).decode("ascii")
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all text from this image exactly as written, preserving structure.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{prepared_mime_type};base64,{encoded}"},
                        },
                    ],
                }
            ],
            temperature=0,
        )
        text = response.choices[0].message.content.strip()
        if not text:
            return "", "No text detected in image."
        return text, None
    except Exception as exc:
        return "", f"Groq vision OCR failed: {exc}"


def _resolve_tesseract_path() -> str | None:
    """Find a usable Tesseract binary path."""
    env_path = os.getenv("TESSERACT_CMD")

    candidate_paths = [
        env_path,
        which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"D:\Tesseract-OCR\tesseract.exe",
    ]

    for candidate in candidate_paths:
        if candidate and Path(candidate).exists():
            return str(candidate)

    return None


def extract_text_from_image(file_bytes: bytes) -> tuple[str, str | None]:
    """Extract text from an image and return (text, warning)."""
    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("L")
    except Exception:
        return "", "Invalid image file."

    if pytesseract is None:
        return extract_text_with_groq_vision(file_bytes)

    tesseract_path = _resolve_tesseract_path()
    if not tesseract_path:
        return extract_text_with_groq_vision(file_bytes)

    pytesseract.pytesseract.tesseract_cmd = tesseract_path

    try:
        text = pytesseract.image_to_string(image, lang="eng").strip()
        if text:
            return text, None
    except Exception:
        pass

    return extract_text_with_groq_vision(file_bytes)
