from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.core.security import bearer_scheme, require_bearer
from app.models.track import Track
from app.services.player_service import PlayerService
from app.services.queue_service import QueueService


class AddQueuePayload(BaseModel):
    track: Track
    requested_by: str | None = None
    play_now: bool = False


class ReorderPayload(BaseModel):
    queue_ids: list[str]


def build_queue_router(queue: QueueService, player: PlayerService, configured_token: str):
    router = APIRouter(prefix="/api/queue")

    def authorize(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> None:
        require_bearer(credentials, configured_token, request.client.host if request.client else "unknown")

    @router.get("")
    async def get_queue(_: None = Depends(authorize)):
        return queue.list()

    @router.post("")
    async def add_to_queue(payload: AddQueuePayload, _: None = Depends(authorize)):
        if payload.play_now:
            if not payload.track.watch_url:
                raise HTTPException(422, "El elemento no tiene una URL reproducible")
            try:
                state = await player.play_url(payload.track.watch_url)
            except RuntimeError as exc:
                raise HTTPException(503, str(exc))
            return {"playing": True, "state": state}
        return await queue.add(payload.track, payload.requested_by)

    @router.delete("/{queue_id}")
    async def remove(queue_id: str, _: None = Depends(authorize)):
        if not await queue.remove(queue_id):
            raise HTTPException(404, "Elemento no encontrado")
        return {"removed": True}

    @router.post("/reorder")
    async def reorder(payload: ReorderPayload, _: None = Depends(authorize)):
        try:
            return await queue.reorder(payload.queue_ids)
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @router.post("/clear")
    async def clear(_: None = Depends(authorize)):
        await queue.clear()
        return {"cleared": True}

    return router
