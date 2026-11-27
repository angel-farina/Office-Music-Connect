import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from app.adapters.chrome_playwright import ChromePlaywrightAdapter
from app.adapters.youtube_search import YouTubeSearchAdapter
from app.api.routes_health import build_health_router
from app.api.routes_player import build_player_router
from app.api.routes_queue import build_queue_router
from app.api.routes_search import build_search_router
from app.api.routes_settings import build_settings_router
from app.api.websocket import build_websocket_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import validate_configured_token
from app.services.events import EventHub
from app.services.chrome_startup import ChromeStartup
from app.services.main_tab_settings import MainTabSettingsService
from app.services.player_service import PlayerService
from app.services.queue_service import QueueService
from app.services.search_service import SearchService


settings = get_settings()
configure_logging(settings.log_level)
validate_configured_token(settings.app_access_token)

events = EventHub()
main_tab_settings = MainTabSettingsService(settings.database_path)
main_tab_url = main_tab_settings.get_main_tab_url(settings.main_tab_url)
browser = ChromePlaywrightAdapter(
    settings.chrome_cdp_url,
    settings.chrome_music_url,
    foreground_url=main_tab_url,
)
player = PlayerService(browser, events)
queue = QueueService(settings.database_path, events)
search = SearchService(YouTubeSearchAdapter())
chrome_startup = ChromeStartup(
    cdp_url=settings.chrome_cdp_url,
    user_data_dir=settings.chrome_user_data_dir,
    startup_urls=[main_tab_url, settings.chrome_music_url],
    executable=settings.chrome_executable,
    auto_launch=settings.chrome_auto_launch,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await chrome_startup.ensure_running()
    except (OSError, RuntimeError, ValueError) as exc:
        logging.getLogger(__name__).error("No se pudo iniciar Chrome: %s", exc)
    await player.start()
    if settings.chrome_auto_launch:
        try:
            await browser.ensure_startup_pages(
                [
                    main_tab_settings.get_main_tab_url(settings.main_tab_url),
                    settings.chrome_music_url,
                ]
            )
        except (RuntimeError, OSError, PlaywrightError, PlaywrightTimeoutError) as exc:
            logging.getLogger(__name__).error("No se pudieron preparar las paginas iniciales: %s", exc)
    yield
    await player.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(build_health_router(settings.device_name))
app.include_router(build_player_router(player, queue, settings.app_access_token))
app.include_router(build_search_router(search, settings.app_access_token))
app.include_router(build_queue_router(queue, player, settings.app_access_token))
app.include_router(
    build_settings_router(
        main_tab_settings,
        browser,
        chrome_startup,
        settings.main_tab_url,
        settings.chrome_music_url,
        settings.app_access_token,
    )
)
app.include_router(build_websocket_router(events, settings.app_access_token))

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def index():
    return FileResponse(static_dir / "index.html")
