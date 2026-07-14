from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import (
    ActionItem,
    Decision,
    KnowledgeDocument,
    Meeting,
    OpenQuestion,
    Project,
    ProjectMemory,
    Risk,
    TranscriptSegment,
)
from app.db.session import get_db
from app.schemas.knowledge import (
    KnowledgeDocumentRead,
    KnowledgeDocumentWrite,
    KnowledgeSearchResult,
)

router = APIRouter()


def _excerpt(content: str, query: str, size: int = 260) -> str:
    normalized = content.strip().replace("\n", " ")
    index = normalized.lower().find(query.lower()) if query else 0
    start = max(0, index - size // 3)
    value = normalized[start : start + size]
    return ("..." if start else "") + value + ("..." if start + size < len(normalized) else "")


def _result(
    *,
    row_id: str,
    source_type: str,
    project_id: str | None,
    meeting_id: str | None,
    title: str,
    content: str,
    query: str,
    created_at: datetime,
    language: str = "und",
    status: str | None = None,
) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        id=row_id,
        source_type=source_type,
        project_id=project_id,
        meeting_id=meeting_id,
        title=title,
        excerpt=_excerpt(content, query),
        language=language,
        status=status,
        created_at=created_at,
    )


@router.post("/knowledge/documents", response_model=KnowledgeDocumentRead, status_code=201)
async def create_document(
    payload: KnowledgeDocumentWrite, db: AsyncSession = Depends(get_db)
) -> KnowledgeDocument:
    if payload.project_id and not await db.get(Project, payload.project_id):
        raise HTTPException(422, "Project not found")
    row = KnowledgeDocument(
        project_id=payload.project_id,
        source_type=payload.source_type,
        title=payload.title,
        content=payload.content,
        language=payload.language,
        metadata_json=payload.metadata,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/knowledge/documents/{document_id}", response_model=KnowledgeDocumentRead)
async def get_document(
    document_id: str, db: AsyncSession = Depends(get_db)
) -> KnowledgeDocument:
    row = await db.get(KnowledgeDocument, document_id)
    if not row:
        raise HTTPException(404, "Knowledge document not found")
    return row


@router.delete("/knowledge/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)) -> None:
    row = await get_document(document_id, db)
    await db.delete(row)
    await db.commit()


@router.get("/knowledge/search", response_model=list[KnowledgeSearchResult])
async def search_knowledge(
    q: str = Query(default="", max_length=300),
    project_id: str | None = None,
    meeting_id: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    language: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeSearchResult]:
    pattern = f"%{q}%"
    results: list[KnowledgeSearchResult] = []
    allowed = {source_type} if source_type else {
        "document",
        "meeting",
        "transcript",
        "decision",
        "action",
        "risk",
        "question",
        "project_memory",
    }

    if "document" in allowed:
        document_query = select(KnowledgeDocument)
        if q:
            document_query = document_query.where(
                or_(
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.content.ilike(pattern),
                )
            )
        if project_id:
            document_query = document_query.where(KnowledgeDocument.project_id == project_id)
        if language:
            document_query = document_query.where(KnowledgeDocument.language == language)
        documents: Sequence[KnowledgeDocument] = (
            await db.scalars(
                document_query.order_by(desc(KnowledgeDocument.updated_at)).limit(limit)
            )
        ).all()
        results.extend(
            _result(
                row_id=row.id,
                source_type="document",
                project_id=row.project_id,
                meeting_id=None,
                title=row.title,
                content=row.content,
                query=q,
                language=row.language,
                created_at=row.created_at,
            )
            for row in documents
        )

    if "meeting" in allowed:
        meeting_query = select(Meeting)
        if q:
            meeting_query = meeting_query.where(
                or_(Meeting.title.ilike(pattern), Meeting.goal.ilike(pattern))
            )
        if project_id:
            meeting_query = meeting_query.where(Meeting.project_id == project_id)
        if meeting_id:
            meeting_query = meeting_query.where(Meeting.id == meeting_id)
        if status:
            meeting_query = meeting_query.where(Meeting.status == status)
        meetings = (
            await db.scalars(meeting_query.order_by(desc(Meeting.created_at)).limit(limit))
        ).all()
        results.extend(
            _result(
                row_id=row.id,
                source_type="meeting",
                project_id=row.project_id,
                meeting_id=row.id,
                title=row.title,
                content=row.goal,
                query=q,
                language=row.language,
                status=row.status,
                created_at=row.created_at,
            )
            for row in meetings
        )

    if "transcript" in allowed:
        transcript_query = select(TranscriptSegment, Meeting.project_id).join(
            Meeting, Meeting.id == TranscriptSegment.meeting_id
        )
        if q:
            transcript_query = transcript_query.where(TranscriptSegment.text.ilike(pattern))
        if project_id:
            transcript_query = transcript_query.where(Meeting.project_id == project_id)
        if meeting_id:
            transcript_query = transcript_query.where(TranscriptSegment.meeting_id == meeting_id)
        if language:
            transcript_query = transcript_query.where(TranscriptSegment.language == language)
        transcript_rows = (await db.execute(transcript_query.limit(limit))).all()
        results.extend(
            _result(
                row_id=row.id,
                source_type="transcript",
                project_id=row_project_id,
                meeting_id=row.meeting_id,
                title=f"Transcript #{row.sequence}",
                content=row.text,
                query=q,
                language=row.language,
                created_at=row.created_at,
            )
            for row, row_project_id in transcript_rows
        )

    state_models: list[tuple[str, Any, Any, Any]] = [
        ("decision", Decision, Decision.title, Decision.description),
        ("action", ActionItem, ActionItem.title, ActionItem.description),
        ("risk", Risk, Risk.content, Risk.content),
        ("question", OpenQuestion, OpenQuestion.content, OpenQuestion.content),
        ("project_memory", ProjectMemory, ProjectMemory.title, ProjectMemory.content),
    ]
    for kind, model, title_column, content_column in state_models:
        if kind not in allowed:
            continue
        query = select(model)
        if q:
            query = query.where(or_(title_column.ilike(pattern), content_column.ilike(pattern)))
        if project_id:
            query = query.where(model.project_id == project_id)
        if meeting_id and hasattr(model, "meeting_id"):
            query = query.where(model.meeting_id == meeting_id)
        if status and hasattr(model, "status"):
            query = query.where(model.status == status)
        rows = (await db.scalars(query.order_by(desc(model.created_at)).limit(limit))).all()
        for row in rows:
            title = str(getattr(row, "title", "") or getattr(row, "content", kind))
            content = str(getattr(row, "description", "") or getattr(row, "content", title))
            results.append(
                _result(
                    row_id=row.id,
                    source_type=kind,
                    project_id=row.project_id,
                    meeting_id=getattr(row, "meeting_id", None),
                    title=title,
                    content=content,
                    query=q,
                    status=getattr(row, "status", None),
                    created_at=row.created_at,
                )
            )

    results.sort(key=lambda row: row.created_at, reverse=True)
    return results[:limit]
