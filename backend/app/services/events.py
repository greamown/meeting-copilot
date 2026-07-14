import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import WebSocket
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Event


class EventHub:
    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, meeting_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients[meeting_id].add(websocket)

    def disconnect(self, meeting_id: str, websocket: WebSocket) -> None:
        self._clients[meeting_id].discard(websocket)

    async def publish(self, meeting_id: str, event: dict[str, Any]) -> None:
        stale = []
        for websocket in self._clients[meeting_id]:
            try:
                await websocket.send_json(event)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(meeting_id, websocket)


hub = EventHub()
event_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def emit(db: AsyncSession, meeting_id: str, event_type: str, source: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with event_locks[meeting_id]:
        sequence = (await db.scalar(select(func.max(Event.sequence)).where(Event.meeting_id == meeting_id)) or 0) + 1
        row = Event(meeting_id=meeting_id, sequence=sequence, type=event_type, source=source, payload_json=payload)
        db.add(row)
        await db.flush()
        envelope = {"event_id": row.id, "meeting_id": meeting_id, "type": event_type, "created_at": datetime.now(timezone.utc).isoformat(), "source": source, "sequence": sequence, "payload": payload}
    await hub.publish(meeting_id, envelope)
    return envelope
