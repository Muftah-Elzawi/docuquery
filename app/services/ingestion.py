import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, Document, DocumentStatus
from app.services.chunking import chunk_pages
from app.services.extraction import extract_fields
from app.services.llm import LLMProvider
from app.services.pdf import extract_pages

log = logging.getLogger(__name__)


def ingest_pdf(db: Session, document: Document, data: bytes, llm: LLMProvider) -> Document:
    """PDF bytes -> page texts -> chunks -> embeddings -> pgvector, plus field extraction."""
    settings = get_settings()
    try:
        pages = extract_pages(data)
        document.pages = len(pages)
        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError("No text found. The PDF is probably a scan; OCR is not enabled yet.")

        vectors = llm.embed([c.content for c in chunks])
        document.chunks = [
            Chunk(
                workspace_id=document.workspace_id,
                page=c.page,
                position=c.position,
                content=c.content,
                embedding=v,
            )
            for c, v in zip(chunks, vectors, strict=True)
        ]
        fields = extract_fields("\n".join(pages), llm)
        document.extracted_fields = fields.model_dump(mode="json")
        document.status = DocumentStatus.ready
        document.error = None
    except Exception as exc:  # store the reason so the user sees why it failed
        log.exception("Ingestion failed for %s", document.filename)
        document.chunks = []
        document.status = DocumentStatus.failed
        document.error = str(exc)
    db.commit()
    db.refresh(document)
    return document
