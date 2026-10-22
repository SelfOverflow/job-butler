"""Live event feed over WebSocket, sourced from the audit log.

Scout sweeps, tailoring, and profile edits run in other processes (CLI,
scheduler), so instead of in-process pub/sub the bus polls `audit_logs` for rows
newer than its cursor and broadcasts them. Every audited action therefore shows
up live, whichever process performed it.
"""

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, sessionmaker

from src.server.routes.audit import AuditOut
from src.storage import repository as repo
from src.storage.models import AuditLog

SNAPSHOT_SIZE = 20
router = APIRouter()


def _serialize(row: AuditLog) -> dict[str, Any]:
    return AuditOut.model_validate(row).model_dump(mode="json")


class EventBus:
    def __init__(self, sessions: sessionmaker[Session], poll_seconds: float) -> None:
        self._sessions, self._poll = sessions, poll_seconds
        self._clients: set[WebSocket] = set()
        self._cursor = 0

    def _snapshot(self) -> list[dict[str, Any]]:
        with self._sessions() as session:
            return [_serialize(r) for r in repo.query_audit(session, limit=SNAPSHOT_SIZE)]

    def _fetch_new(self) -> list[dict[str, Any]]:
        with self._sessions() as session:
            rows = repo.audit_after(session, self._cursor)
            if rows:
                self._cursor = rows[-1][0]
            return [_serialize(row) for _, row in rows]

    def _latest(self) -> int:
        with self._sessions() as session:
            return repo.latest_audit_rowid(session)

    async def start(self) -> None:
        """Begin after the newest existing event; history is served via snapshots."""
        self._cursor = await asyncio.to_thread(self._latest)

    async def run(self) -> None:
        while True:
            for event in await asyncio.to_thread(self._fetch_new):
                await self.broadcast({"type": "audit", "event": event})
            await asyncio.sleep(self._poll)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        snapshot = await asyncio.to_thread(self._snapshot)
        await ws.send_json({"type": "snapshot", "events": snapshot})
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:  # Closed or broken socket: drop it, keep serving others.
                self.disconnect(ws)


@router.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    bus: EventBus = ws.app.state.bus
    await bus.connect(ws)
    try:
        while True:
            await ws.receive_text()  # Client messages are ignored; this detects disconnects.
    except WebSocketDisconnect:
        bus.disconnect(ws)
