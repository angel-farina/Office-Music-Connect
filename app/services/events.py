from asyncio import Lock
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket


def event(type_: str, data: Any) -> dict:
    return {
        "type": type_,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


class EventHub:
    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def publish(self, type_: str, data: Any) -> None:
        payload = event(type_, data)
        async with self._lock:
            clients = list(self._clients)
        disconnected = []
        for websocket in clients:
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            await self.disconnect(websocket)
