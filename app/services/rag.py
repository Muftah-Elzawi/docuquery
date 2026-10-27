import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Chunk, Document, DocumentStatus
from app.services.llm import LLMProvider

SYSTEM_PROMPT = """You answer questions about the user's documents.
Rules:
- Use ONLY the numbered sources provided. Never use outside knowledge.
- Cite every statement with its source number in square brackets, e.g. [1] or [2][3].
- If the sources do not contain the answer, say so plainly. Do not guess.
- Answer in the language of the question."""

NO_ANSWER = "I couldn't find this in your documents."


@dataclass
class Source:
    number: int
    document_id: str
    filename: str
    page: int
    similarity: float
    excerpt: str


@dataclass
class Answer:
    answer: str
    sources: list[Source]


def retrieve(
    db: Session, workspace_id: str, query_vector: list[float], top_k: int, document_ids: list[str] | None = None
) -> list[tuple[Chunk, str, float]]:
    """Cosine search in pgvector, ALWAYS scoped to one workspace (tenant isolation)."""
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(Chunk, Document.filename, distance)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.workspace_id == workspace_id, Document.status == DocumentStatus.ready)
        .order_by(distance)
        .limit(top_k)
    )
    if document_ids:
        stmt = stmt.where(Chunk.document_id.in_(document_ids))
    return [(chunk, filename, 1 - dist) for chunk, filename, dist in db.execute(stmt).all()]


def answer_question(
    db: Session, workspace_id: str, question: str, llm: LLMProvider, document_ids: list[str] | None = None
) -> Answer:
    settings = get_settings()
    [query_vector] = llm.embed([question])
    hits = [
        h for h in retrieve(db, workspace_id, query_vector, settings.top_k, document_ids)
        if h[2] >= settings.min_similarity
    ]
    if not hits:
        return Answer(answer=NO_ANSWER, sources=[])

    sources = [
        Source(i, chunk.document_id, filename, chunk.page, round(sim, 3), chunk.content[:400])
        for i, (chunk, filename, sim) in enumerate(hits, start=1)
    ]
    context = "\n\n".join(
        f"[{s.number}] {s.filename}, page {s.page}\n{chunk.content}"
        for s, (chunk, _, _) in zip(sources, hits)
    )
    # The reminder sits at the end of the prompt, where small local models pay most attention.
    prompt = f"Sources:\n{context}\n\nQuestion: {question}\n\nAnswer and cite the source numbers like [1]."
    reply = llm.chat(SYSTEM_PROMPT, prompt)
    return Answer(answer=remove_invalid_citations(reply, len(sources)), sources=sources)


def remove_invalid_citations(text: str, source_count: int) -> str:
    """Drop citation markers like [7] that point to no source, so every visible citation is checkable."""
    keep_valid = lambda m: m.group(0) if 1 <= int(m.group(2)) <= source_count else ""  # noqa: E731
    return re.sub(r"( ?)\[(\d+)\]", keep_valid, text).strip()
