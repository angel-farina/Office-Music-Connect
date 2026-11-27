from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import AnyHttpUrl, BaseModel, Field

from app.adapters.chrome_playwright import ChromePlaywrightAdapter
from app.core.security import bearer_scheme, require_bearer
from app.services.chrome_startup import ChromeStartup
from app.services.main_tab_settings import MainTabSettingsService


class MainTabSettingsPayload(BaseModel):
    url: AnyHttpUrl = Field(max_length=2048)


def build_settings_router(
    settings_service: MainTabSettingsService,
    browser: ChromePlaywrightAdapter,
    chrome_startup: ChromeStartup,
    default_url: str,
    music_url: str,
    configured_token: str,
):
    router = APIRouter(prefix="/api/settings")

    def authorize(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> None:
        require_bearer(
            credentials,
            configured_token,
            request.client.host if request.client else "unknown",
        )

    @router.get("")
    async def get_settings(_: None = Depends(authorize)):
        return {"main_tab_url": settings_service.get_main_tab_url(default_url)}

    @router.put("/main-tab")
    async def set_main_tab(
        payload: MainTabSettingsPayload,
        _: None = Depends(authorize),
    ):
        url = str(payload.url)
        if urlparse(url).hostname == urlparse(music_url).hostname:
            raise HTTPException(422, "La pestaña principal no puede ser YouTube Music")

        settings_service.set_main_tab_url(url)
        if chrome_startup.startup_urls:
            chrome_startup.startup_urls[0] = url
        else:
            chrome_startup.startup_urls.append(url)
        try:
            applied = await browser.set_foreground_url(url)
        except RuntimeError as exc:
            raise HTTPException(
                503,
                f"El enlace se guardo, pero no se pudo aplicar en Chrome: {exc}",
            ) from exc
        return {"main_tab_url": url, "applied": applied}

    return router
