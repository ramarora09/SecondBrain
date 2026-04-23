"""OCR extraction with optional pytesseract support."""

from __future__ import annotations

import io
import os
from pathlib import Path
from shutil import which

from PIL import Image

try:
    import pytesseract
except Exception:
    pytesseract = None


def _resolve_tesseract_path() -> str | None:
    """Find a usable Tesseract binary path."""
    
    env_path = os.getenv("TESSERACT_CMD")

    candidate_paths = [
        env_path,
        which("tesseract"),  # works if PATH is set
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"D:\Tesseract-OCR\tesseract.exe",  # 🔥 support custom install
    ]

    for candidate in candidate_paths:
        if candidate and Path(candidate).exists():
            return str(candidate)

    return None


def extract_text_from_image(file_bytes: bytes) -> tuple[str, str | None]:
    """Extract text from an image and return (text, warning)."""

    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("L")  # grayscale
    except Exception:
        return "", "⚠️ Invalid image file"

    if pytesseract is None:
        return "", "⚠️ pytesseract not installed"

    tesseract_path = _resolve_tesseract_path()
    if not tesseract_path:
        return "", "⚠️ Tesseract not found. Install it or set TESSERACT_CMD"

    pytesseract.pytesseract.tesseract_cmd = tesseract_path

    try:
        text = pytesseract.image_to_string(image, lang="eng").strip()

        if not text:
            return "", "⚠️ No text detected in image"

        return text, None

    except Exception as exc:
        return "", f"⚠️ OCR failed: {str(exc)}"