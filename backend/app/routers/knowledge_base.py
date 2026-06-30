"""Research Hub + Internal Knowledge Base API.

Document ingestion, deterministic TF-IDF retrieval, RAG Q&A, and summarization.
Every analytical/AI output is wrapped with the compliance layer before it
leaves the system, and writes are recorded in the audit trail.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.deps import get_current_verified_user, record_audit, require_role
from mirrorquant_demo import compliance, knowledge_base
from mirrorquant_demo.database import get_session
from mirrorquant_demo.models import User
from mirrorquant_demo.permissions import ANALYST

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


# --- request bodies ---------------------------------------------------------
class IngestRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=1)
    kind: str = Field(default="text", max_length=32)
    source_name: str | None = Field(default=None, max_length=255)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


# --- serialization ----------------------------------------------------------
def _document_out(document) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "source_name": document.source_name,
        "kind": document.kind,
        "char_count": document.char_count,
        "created_at": document.created_at,
    }


# --- endpoints --------------------------------------------------------------
@router.post("/documents")
async def ingest_document(
    body: IngestRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_role(ANALYST)),
) -> dict:
    try:
        document = knowledge_base.ingest_document(
            session,
            user_id=current_user.id,
            title=body.title,
            text=body.text,
            kind=body.kind,
            source_name=body.source_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        session,
        user_id=current_user.id,
        action="kb.ingest",
        target_type="kb_document",
        target_id=document.id,
        detail={"title": document.title, "kind": document.kind, "char_count": document.char_count},
        request=request,
    )

    out = _document_out(document)
    out["chunk_count"] = len(document.chunks)
    return out


@router.get("/documents")
async def list_documents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
) -> list[dict]:
    documents = knowledge_base.list_documents(session, current_user.id)
    return [_document_out(doc) for doc in documents]


@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
) -> dict:
    try:
        document = knowledge_base.get_document(session, current_user.id, doc_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    out = _document_out(document)
    out["chunk_count"] = len(document.chunks)
    return out


@router.post("/search")
async def search(
    body: SearchRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
) -> dict:
    try:
        results = knowledge_base.search_chunks(
            session, current_user.id, body.query, top_k=body.top_k
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload = {"query": body.query, "top_k": body.top_k, "results": results}
    return compliance.attach_compliance(
        payload,
        sources=[
            compliance.source(
                "knowledge_base",
                f"doc:{item['document_id']}#chunk{item['chunk_index']}",
                item["document_title"],
            )
            for item in results
        ],
    )


@router.post("/ask")
async def ask(
    body: AskRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
) -> dict:
    try:
        answer = await knowledge_base.answer_question(
            session, current_user.id, body.query, top_k=body.top_k
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return compliance.attach_compliance(
        answer,
        sources=[
            compliance.source(
                "knowledge_base",
                f"chunk{src['chunk_index']}",
                src["document_title"],
            )
            for src in answer.get("sources", [])
        ],
    )


@router.post("/documents/{doc_id}/summary")
async def summarize(
    doc_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_verified_user),
) -> dict:
    try:
        summary = await knowledge_base.summarize_document(session, current_user.id, doc_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return compliance.attach_compliance(
        summary,
        sources=[
            compliance.source("knowledge_base", f"doc:{summary['document_id']}", summary["title"])
        ],
    )
