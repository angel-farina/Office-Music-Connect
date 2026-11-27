from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.core.security import bearer_scheme, require_bearer
from app.services.player_service import PlayerService
from app.services.queue_service import QueueService


class SeekPayload(BaseModel):
    position_seconds: float = Field(ge=0, allow_inf_nan=False)


def build_player_router(player: PlayerService, queue: QueueService, configured_token: str):
    router = APIRouter(prefix="/api/player")

    def authorize(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> None:
        require_bearer(credentials, configured_token, request.client.host if request.client else "unknown")

    @router.get("")
    async def get_player():
        return await player.get_state()

    @router.post("/play")
    async def play(_: None = Depends(authorize)):
        try:
            return await player.play()
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))

    @router.post("/pause")
    async def pause(_: None = Depends(authorize)):
        try:
            return await player.pause()
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))

    @router.post("/next")
    async def next_track(_: None = Depends(authorize)):
        try:
            return await player.next(queue)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))

    @router.post("/previous")
    async def previous_track(_: None = Depends(authorize)):
        try:
            return await player.previous()
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))

    @router.post("/volume")
    async def set_volume(payload: dict, _: None = Depends(authorize)):
        volume = payload.get("volume")
        if not isinstance(volume, int) or not 0 <= volume <= 100:
            raise HTTPException(422, "volume debe ser un entero entre 0 y 100")
        try:
            return await player.set_volume(volume)
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))

    @router.post("/seek")
    async def seek(payload: SeekPayload, _: None = Depends(authorize)):
        try:
            return await player.seek(payload.position_seconds)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))

    return router
