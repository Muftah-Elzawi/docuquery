import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    page: int        # 1-based page number, kept so answers can cite their source
    position: int    # order of the chunk within the document
    content: str


def _normalise(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def chunk_pages(pages: list[str], size: int = 900, overlap: int = 150) -> list[TextChunk]:
    """Split page texts into overlapping chunks that never cross a page boundary.

    Cuts prefer paragraph breaks, then sentence ends, then spaces, so a chunk rarely
    ends mid-word. Overlap keeps facts that sit on a cut available in both chunks.
    """
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    chunks: list[TextChunk] = []
    for page_no, raw in enumerate(pages, start=1):
        text = _normalise(raw)
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                window = text[start:end]
                # Only accept a natural break in the second half of the window,
                # otherwise chunks would become very small.
                for sep in ("\n\n", ". ", "\n", " "):
                    cut = window.rfind(sep)
                    if cut > size // 2:
                        end = start + cut + len(sep)
                        break
            piece = text[start:end].strip()
            if piece:
                chunks.append(TextChunk(page=page_no, position=len(chunks), content=piece))
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
    return chunks
