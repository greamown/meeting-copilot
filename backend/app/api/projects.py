from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Meeting, Project, ProjectGlossary, ProjectMemory
from app.db.session import get_db
from app.schemas.project import (
    GlossaryBase,
    GlossaryRead,
    ProjectBase,
    ProjectDetail,
    ProjectMemoryBase,
    ProjectMemoryRead,
    ProjectRead,
)

router = APIRouter()


async def require_project(db: AsyncSession, project_id: str) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def glossary_read(row: ProjectGlossary) -> GlossaryRead:
    return GlossaryRead(
        id=row.id,
        project_id=row.project_id,
        term=row.term,
        language=row.language,
        preferred_spelling=row.preferred_spelling,
        translation=row.translation,
        description=row.description,
        aliases=list(row.aliases_json or []),
        do_not_translate=row.do_not_translate,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/projects", response_model=list[ProjectRead])
async def list_projects(
    q: str | None = Query(default=None, max_length=200), db: AsyncSession = Depends(get_db)
) -> list[Project]:
    query = select(Project).order_by(desc(Project.updated_at))
    if q:
        pattern = f"%{q}%"
        query = query.where(or_(Project.name.ilike(pattern), Project.description.ilike(pattern)))
    return list((await db.scalars(query)).all())


@router.post("/projects", response_model=ProjectRead, status_code=201)
async def create_project(payload: ProjectBase, db: AsyncSession = Depends(get_db)) -> Project:
    row = Project(**payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)) -> ProjectDetail:
    row = await require_project(db, project_id)
    counts: dict[str, Any] = {}
    for name, model in (
        ("meeting_count", Meeting),
        ("memory_count", ProjectMemory),
        ("glossary_count", ProjectGlossary),
    ):
        counts[name] = (
            await db.scalar(
                select(func.count()).select_from(model).where(model.project_id == project_id)
            )
            or 0
        )
    return ProjectDetail(**ProjectRead.model_validate(row).model_dump(), **counts)


@router.put("/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: str, payload: ProjectBase, db: AsyncSession = Depends(get_db)
) -> Project:
    row = await require_project(db, project_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)) -> None:
    row = await require_project(db, project_id)
    await db.delete(row)
    await db.commit()


@router.get("/projects/{project_id}/glossary", response_model=list[GlossaryRead])
async def list_glossary(
    project_id: str,
    q: str | None = Query(default=None, max_length=200),
    db: AsyncSession = Depends(get_db),
) -> list[GlossaryRead]:
    await require_project(db, project_id)
    query = select(ProjectGlossary).where(ProjectGlossary.project_id == project_id)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(ProjectGlossary.term.ilike(pattern), ProjectGlossary.description.ilike(pattern))
        )
    rows = (await db.scalars(query.order_by(ProjectGlossary.term))).all()
    return [glossary_read(row) for row in rows]


@router.post("/projects/{project_id}/glossary", response_model=GlossaryRead, status_code=201)
async def create_glossary(
    project_id: str, payload: GlossaryBase, db: AsyncSession = Depends(get_db)
) -> GlossaryRead:
    await require_project(db, project_id)
    values = payload.model_dump(exclude={"aliases"})
    row = ProjectGlossary(project_id=project_id, aliases_json=payload.aliases, **values)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Glossary term already exists for this language") from exc
    await db.refresh(row)
    return glossary_read(row)


@router.put("/project-glossary/{entry_id}", response_model=GlossaryRead)
async def update_glossary(
    entry_id: str, payload: GlossaryBase, db: AsyncSession = Depends(get_db)
) -> GlossaryRead:
    row = await db.get(ProjectGlossary, entry_id)
    if not row:
        raise HTTPException(404, "Glossary entry not found")
    for key, value in payload.model_dump(exclude={"aliases"}).items():
        setattr(row, key, value)
    row.aliases_json = payload.aliases
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Glossary term already exists for this language") from exc
    await db.refresh(row)
    return glossary_read(row)


@router.delete("/project-glossary/{entry_id}", status_code=204)
async def delete_glossary(entry_id: str, db: AsyncSession = Depends(get_db)) -> None:
    row = await db.get(ProjectGlossary, entry_id)
    if not row:
        raise HTTPException(404, "Glossary entry not found")
    await db.delete(row)
    await db.commit()


@router.get("/projects/{project_id}/memory", response_model=list[ProjectMemoryRead])
async def list_memory(
    project_id: str,
    q: str | None = Query(default=None, max_length=200),
    category: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[ProjectMemory]:
    await require_project(db, project_id)
    query = select(ProjectMemory).where(ProjectMemory.project_id == project_id)
    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(ProjectMemory.title.ilike(pattern), ProjectMemory.content.ilike(pattern))
        )
    if category:
        query = query.where(ProjectMemory.category == category)
    if status:
        query = query.where(ProjectMemory.status == status)
    return list((await db.scalars(query.order_by(desc(ProjectMemory.updated_at)))).all())


@router.post("/projects/{project_id}/memory", response_model=ProjectMemoryRead, status_code=201)
async def create_memory(
    project_id: str, payload: ProjectMemoryBase, db: AsyncSession = Depends(get_db)
) -> ProjectMemory:
    await require_project(db, project_id)
    row = ProjectMemory(project_id=project_id, **payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/project-memory/{memory_id}", response_model=ProjectMemoryRead)
async def update_memory(
    memory_id: str, payload: ProjectMemoryBase, db: AsyncSession = Depends(get_db)
) -> ProjectMemory:
    row = await db.get(ProjectMemory, memory_id)
    if not row:
        raise HTTPException(404, "Project memory not found")
    changed = row.title != payload.title or row.content != payload.content
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    if changed:
        row.version += 1
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/project-memory/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, db: AsyncSession = Depends(get_db)) -> None:
    row = await db.get(ProjectMemory, memory_id)
    if not row:
        raise HTTPException(404, "Project memory not found")
    await db.delete(row)
    await db.commit()
