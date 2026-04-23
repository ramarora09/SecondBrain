import io
import os

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

def extract_text(file_bytes):
    max_pages = int(os.getenv("PDF_MAX_PAGES", "30"))
    max_chars = int(os.getenv("PDF_MAX_CHARS", "100000"))

    try:
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

        return "".join(parts)

    except Exception as e:
        print("PDF ERROR:", str(e))
        return ""
