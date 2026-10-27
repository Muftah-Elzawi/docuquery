from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from app.config import get_settings
from app.models import Document, Role
from app.schemas import AskRequest, AskResponse, DocumentOut
from app.security import CurrentUser, DbSession
from app.services.ingestion import ingest_pdf
from app.services.llm import LLMError, get_llm
from app.services.rag import answer_question

router = APIRouter(prefix="/api", tags=["documents"])


def _get_owned_document(db, user, document_id: str) -> Document:
    doc = db.get(Document, document_id)
    # A document from another workspace is reported as "not found", never as "forbidden",
    # so its existence isn't leaked across tenants.
    if doc is None or doc.workspace_id != user.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return doc


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(file: UploadFile, user: CurrentUser, db: DbSession):
    # A plain `def` endpoint runs in a worker thread, so the blocking embedding calls
    # don't freeze the event loop for other requests.
    settings = get_settings()
    data = file.file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Max {settings.max_upload_mb} MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF files are supported")

    doc = Document(workspace_id=user.workspace_id, uploaded_by=user.id, filename=file.filename or "upload.pdf")
    db.add(doc)
    db.commit()
    return ingest_pdf(db, doc, data, get_llm())


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(user: CurrentUser, db: DbSession):
    stmt = select(Document).where(Document.workspace_id == user.workspace_id).order_by(Document.created_at.desc())
    return db.scalars(stmt).all()


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, user: CurrentUser, db: DbSession):
    return _get_owned_document(db, user, document_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, user: CurrentUser, db: DbSession):
    doc = _get_owned_document(db, user, document_id)
    if user.role != Role.admin and doc.uploaded_by != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can delete other people's documents")
    db.delete(doc)
    db.commit()


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, user: CurrentUser, db: DbSession):
    try:
        result = answer_question(db, user.workspace_id, body.question, get_llm(), body.document_ids)
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return AskResponse(answer=result.answer, sources=[s.__dict__ for s in result.sources])
