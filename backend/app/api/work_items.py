from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import ActionItem, Decision, Meeting, Project, TranscriptSegment
from app.db.session import get_db
from app.schemas.knowledge import (
    ActionRead,
    ActionWrite,
    DecisionRead,
    DecisionSupersede,
    DecisionWrite,
)

router = APIRouter()


async def _meeting_project(
    db: AsyncSession, meeting_id: str, requested_project_id: str | None
) -> tuple[Meeting, str | None]:
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(422, "Meeting not found")
    if requested_project_id and requested_project_id != meeting.project_id:
        raise HTTPException(422, "Project does not match the meeting")
    if requested_project_id and not await db.get(Project, requested_project_id):
        raise HTTPException(422, "Project not found")
    return meeting, meeting.project_id


async def _validate_evidence(
    db: AsyncSession, meeting_id: str, segment_ids: list[str]
) -> None:
    if not segment_ids:
        return
    found = set(
        (
            await db.scalars(
                select(TranscriptSegment.id).where(
                    TranscriptSegment.meeting_id == meeting_id,
                    TranscriptSegment.id.in_(segment_ids),
                )
            )
        ).all()
    )
    if found != set(segment_ids):
        raise HTTPException(422, "Evidence contains transcript segments from another meeting")


def _decision_values(
    payload: DecisionWrite | DecisionSupersede, project_id: str | None
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "title": payload.title,
        "description": payload.description,
        "content": payload.description or payload.title,
        "owner": payload.owner,
        "status": payload.status,
        "confidence": payload.confidence,
        "evidence_segment_ids_json": payload.evidence_segment_ids,
    }


@router.get("/decisions", response_model=list[DecisionRead])
async def list_decisions(
    q: str | None = Query(default=None, max_length=300),
    project_id: str | None = None,
    meeting_id: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[Decision]:
    query = select(Decision)
    if q:
        pattern = f"%{q}%"
        query = query.where(or_(Decision.title.ilike(pattern), Decision.description.ilike(pattern)))
    if project_id:
        query = query.where(Decision.project_id == project_id)
    if meeting_id:
        query = query.where(Decision.meeting_id == meeting_id)
    if status:
        query = query.where(Decision.status == status)
    if owner:
        query = query.where(Decision.owner == owner)
    if date_from:
        query = query.where(Decision.created_at >= date_from)
    if date_to:
        query = query.where(Decision.created_at <= date_to)
    return list((await db.scalars(query.order_by(desc(Decision.created_at)).limit(500))).all())


@router.post("/decisions", response_model=DecisionRead, status_code=201)
async def create_decision(
    payload: DecisionWrite, db: AsyncSession = Depends(get_db)
) -> Decision:
    _, project_id = await _meeting_project(db, payload.meeting_id, payload.project_id)
    await _validate_evidence(db, payload.meeting_id, payload.evidence_segment_ids)
    row = Decision(
        meeting_id=payload.meeting_id,
        source="user",
        **_decision_values(payload, project_id),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/decisions/{decision_id}", response_model=DecisionRead)
async def get_decision(decision_id: str, db: AsyncSession = Depends(get_db)) -> Decision:
    row = await db.get(Decision, decision_id)
    if not row:
        raise HTTPException(404, "Decision not found")
    return row


async def _supersede(
    row: Decision, payload: DecisionSupersede, db: AsyncSession
) -> Decision:
    if row.status == "superseded":
        raise HTTPException(409, "Decision has already been superseded")
    await _validate_evidence(db, row.meeting_id, payload.evidence_segment_ids)
    replacement = Decision(
        meeting_id=row.meeting_id,
        source="user",
        version=row.version + 1,
        supersedes_id=row.id,
        **_decision_values(payload, row.project_id),
    )
    db.add(replacement)
    await db.flush()
    row.status = "superseded"
    row.superseded_by_id = replacement.id
    row.updated_by = "user"
    await db.commit()
    await db.refresh(replacement)
    return replacement


@router.put("/decisions/{decision_id}", response_model=DecisionRead)
async def update_decision(
    decision_id: str, payload: DecisionWrite, db: AsyncSession = Depends(get_db)
) -> Decision:
    row = await get_decision(decision_id, db)
    if payload.meeting_id != row.meeting_id or payload.project_id not in (None, row.project_id):
        raise HTTPException(422, "A decision version cannot move to another meeting or project")
    return await _supersede(
        row,
        DecisionSupersede(**payload.model_dump(exclude={"meeting_id", "project_id"})),
        db,
    )


@router.post("/decisions/{decision_id}/confirm", response_model=DecisionRead)
async def confirm_decision(decision_id: str, db: AsyncSession = Depends(get_db)) -> Decision:
    row = await get_decision(decision_id, db)
    if row.status in ("rejected", "superseded", "archived"):
        raise HTTPException(409, f"Cannot confirm a {row.status} decision")
    row.status = "confirmed"
    row.updated_by = "user"
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/decisions/{decision_id}/reject", response_model=DecisionRead)
async def reject_decision(decision_id: str, db: AsyncSession = Depends(get_db)) -> Decision:
    row = await get_decision(decision_id, db)
    if row.status in ("confirmed", "superseded", "archived"):
        raise HTTPException(409, f"Cannot reject a {row.status} decision")
    row.status = "rejected"
    row.updated_by = "user"
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/decisions/{decision_id}/supersede", response_model=DecisionRead, status_code=201)
async def supersede_decision(
    decision_id: str, payload: DecisionSupersede, db: AsyncSession = Depends(get_db)
) -> Decision:
    return await _supersede(await get_decision(decision_id, db), payload, db)


@router.get("/actions", response_model=list[ActionRead])
async def list_actions(
    q: str | None = Query(default=None, max_length=300),
    project_id: str | None = None,
    meeting_id: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    priority: str | None = None,
    due_before: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[ActionItem]:
    query = select(ActionItem)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(ActionItem.title.ilike(pattern), ActionItem.description.ilike(pattern))
        )
    for column, value in (
        (ActionItem.project_id, project_id),
        (ActionItem.meeting_id, meeting_id),
        (ActionItem.status, status),
        (ActionItem.owner, owner),
        (ActionItem.priority, priority),
    ):
        if value:
            query = query.where(column == value)
    if due_before:
        query = query.where(ActionItem.due_at <= due_before)
    rows = await db.scalars(query.order_by(ActionItem.due_at, desc(ActionItem.created_at)))
    return list(rows.all())


async def _action_values(payload: ActionWrite, db: AsyncSession) -> dict[str, Any]:
    _, project_id = await _meeting_project(db, payload.meeting_id, payload.project_id)
    await _validate_evidence(db, payload.meeting_id, payload.evidence_segment_ids)
    if payload.linked_decision_id:
        decision = await db.get(Decision, payload.linked_decision_id)
        if not decision or decision.meeting_id != payload.meeting_id:
            raise HTTPException(422, "Linked decision must belong to the same meeting")
    return {
        "meeting_id": payload.meeting_id,
        "project_id": project_id,
        "title": payload.title,
        "description": payload.description,
        "content": payload.description or payload.title,
        "owner": payload.owner,
        "due_at": payload.due_at,
        "priority": payload.priority,
        "status": payload.status,
        "linked_decision_id": payload.linked_decision_id,
        "evidence_segment_ids_json": payload.evidence_segment_ids,
    }


@router.post("/actions", response_model=ActionRead, status_code=201)
async def create_action(payload: ActionWrite, db: AsyncSession = Depends(get_db)) -> ActionItem:
    row = ActionItem(source="user", **await _action_values(payload, db))
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/actions/{action_id}", response_model=ActionRead)
async def get_action(action_id: str, db: AsyncSession = Depends(get_db)) -> ActionItem:
    row = await db.get(ActionItem, action_id)
    if not row:
        raise HTTPException(404, "Action item not found")
    return row


@router.put("/actions/{action_id}", response_model=ActionRead)
async def update_action(
    action_id: str, payload: ActionWrite, db: AsyncSession = Depends(get_db)
) -> ActionItem:
    row = await get_action(action_id, db)
    for key, value in (await _action_values(payload, db)).items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/actions/{action_id}", status_code=204)
async def delete_action(action_id: str, db: AsyncSession = Depends(get_db)) -> None:
    row = await get_action(action_id, db)
    await db.delete(row)
    await db.commit()
