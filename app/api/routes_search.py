from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import bearer_scheme, require_bearer
from app.services.search_service import SearchService


def build_search_router(search: SearchService, configured_token: str):
    router = APIRouter(prefix="/api/search")

    def authorize(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> None:
        require_bearer(credentials, configured_token, request.client.host if request.client else "unknown")

    @router.get("")
    async def search_tracks(
        q: str = Query(..., min_length=1, max_length=200),
        limit: int = Query(20, ge=1, le=50),
        _: None = Depends(authorize),
    ):
        try:
            return await search.search(q, limit)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
        except RuntimeError as exc:
            raise HTTPException(503, str(exc))

    return router
