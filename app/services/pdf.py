import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfExtractionError(ValueError):
    pass


def extract_pages(data: bytes) -> list[str]:
    """Return the text of each page. Scanned PDFs without a text layer return empty strings."""
    try:
        reader = PdfReader(io.BytesIO(data))
        return [(page.extract_text() or "").strip() for page in reader.pages]
    except PdfReadError as exc:
        raise PdfExtractionError(f"Could not read PDF: {exc}") from exc
