from fastapi import APIRouter


router = APIRouter(prefix="/api")


def build_health_router(device_name: str):
    @router.get("/health")
    async def health():
        return {
            "status": "ok",
            "device": device_name,
            "service": "Office Music Connect",
        }

    return router
