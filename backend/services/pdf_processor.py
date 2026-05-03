import io
import os

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    import fitz
except Exception:
    fitz = None


def _extract_with_pypdf(file_bytes: bytes, max_pages: int, max_chars: int) -> str:
    if PdfReader is None:
        return ""

    pdf = PdfReader(io.BytesIO(file_bytes))
    parts = []
    total_chars = 0

    for index, page in enumerate(pdf.pages):
        if index >= max_pages or total_chars >= max_chars:
            break
        content = page.extract_text()
        if content:
            remaining = max_chars - total_chars
            trimmed = content[:remaining]
            parts.append(trimmed)
            total_chars += len(trimmed)

    return "\n\n".join(parts)


def _extract_with_pymupdf(file_bytes: bytes, max_pages: int, max_chars: int) -> str:
    if fitz is None:
        return ""

    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    parts = []
    total_chars = 0

    for index, page in enumerate(pdf):
        if index >= max_pages or total_chars >= max_chars:
            break
        content = page.get_text("text")
        if content:
            remaining = max_chars - total_chars
            trimmed = content[:remaining]
            parts.append(trimmed)
            total_chars += len(trimmed)

    return "\n\n".join(parts)


def extract_text(file_bytes):
    max_pages = int(os.getenv("PDF_MAX_PAGES", "500"))
    max_chars = int(os.getenv("PDF_MAX_CHARS", "500000"))

    try:
        text = _extract_with_pypdf(file_bytes, max_pages, max_chars)
        if text.strip():
            return text

        return _extract_with_pymupdf(file_bytes, max_pages, max_chars)

    except Exception as e:
        print("PDF ERROR:", str(e))
        try:
            return _extract_with_pymupdf(file_bytes, max_pages, max_chars)
        except Exception as fallback_error:
            print("PDF FALLBACK ERROR:", str(fallback_error))
            return ""
