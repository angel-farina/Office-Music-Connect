from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import require_websocket_token
from app.services.events import EventHub


def build_websocket_router(events: EventHub, configured_token: str):
    router = APIRouter()

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await require_websocket_token(websocket, configured_token)
        await events.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await events.disconnect(websocket)

    return router
