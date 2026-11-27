import asyncio
import logging
import math
from urllib.parse import parse_qs, urlparse

from playwright.async_api import (
    Error as PlaywrightError,
    async_playwright,
    Browser,
    CDPSession,
    Page,
)

from app.adapters.browser_base import BrowserAdapter
from app.models.player import PlayerState, utc_now
from app.models.track import Track


LOGGER = logging.getLogger(__name__)


class ChromePlaywrightAdapter(BrowserAdapter):
    def __init__(self, cdp_url: str, music_url: str, foreground_url: str | None = None):
        self.cdp_url = cdp_url
        self.music_url = music_url
        self.foreground_url = foreground_url
        self._playwright = None
        self._browser: Browser | None = None
        self._page: Page | None = None
        self._volume: int | None = None
        self._retry_delay = 1

    async def connect(self) -> bool:
        try:
            if self._browser:
                return await self._find_music_page()
            if not self._playwright:
                self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
            return await self._find_music_page()
        except Exception as exc:
            LOGGER.warning("No se pudo conectar a Chrome CDP: %s", exc)
            self._page = None
            return False

    async def close(self) -> None:
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._page = None

    async def _find_music_page(self) -> bool:
        if not self._browser:
            return False
        for context in self._browser.contexts:
            for page in context.pages:
                try:
                    if urlparse(page.url).hostname == "music.youtube.com":
                        self._page = page
                        return True
                except Exception:
                    continue
        self._page = None
        return False

    async def ensure_startup_pages(self, urls: list[str]) -> None:
        if not await self.connect() or not self._browser:
            raise RuntimeError("No se pudo conectar al Chrome dedicado para abrir las paginas iniciales")
        if not self.foreground_url and urls:
            self.foreground_url = urls[0]
        context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()
        for url in urls:
            if any(self._same_startup_page(page.url, url) for page in context.pages):
                continue
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await self._focus_foreground_page()

    async def set_foreground_url(self, url: str) -> bool:
        previous_host = urlparse(self.foreground_url or "").hostname
        self.foreground_url = url
        if not self._browser:
            await self.connect()
        if not self._browser:
            return False

        page = None
        if previous_host:
            for context in self._browser.contexts:
                page = next(
                    (
                        candidate
                        for candidate in context.pages
                        if urlparse(candidate.url).hostname == previous_host
                    ),
                    None,
                )
                if page:
                    break

        try:
            if page is None:
                context = (
                    self._browser.contexts[0]
                    if self._browser.contexts
                    else await self._browser.new_context()
                )
                page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.bring_to_front()
            await self.ensure_fullscreen()
        except PlaywrightError as exc:
            raise RuntimeError("No se pudo abrir la pestaña principal configurada") from exc
        return True

    async def ensure_fullscreen(self) -> None:
        if not self._browser and not await self.connect():
            raise RuntimeError("No se pudo conectar a Chrome para activar pantalla completa")
        if not self._browser:
            raise RuntimeError("Chrome no esta disponible para activar pantalla completa")
        session = await self._browser.new_browser_cdp_session()
        await self._set_session_fullscreen(session)

    async def _set_session_fullscreen(self, session: CDPSession) -> None:
        try:
            window = await session.send("Browser.getWindowForTarget")
            if window.get("bounds", {}).get("windowState") != "fullscreen":
                await session.send(
                    "Browser.setWindowBounds",
                    {
                        "windowId": window["windowId"],
                        "bounds": {"windowState": "fullscreen"},
                    },
                )
        except PlaywrightError as exc:
            raise RuntimeError("No se pudo iniciar Chrome en pantalla completa") from exc
        finally:
            await session.detach()



    @staticmethod
    def _same_startup_page(current_url: str, startup_url: str) -> bool:
        current = urlparse(current_url)
        startup = urlparse(startup_url)
        if current.scheme != startup.scheme or current.hostname != startup.hostname:
            return False
        if startup.path in ("", "/"):
            return True
        return current.path.rstrip("/") == startup.path.rstrip("/")

    async def _ensure_page(self) -> Page:
        if not await self._find_music_page():
            raise RuntimeError("YouTube Music no esta abierto en el Chrome dedicado")
        if not self._page:
            raise RuntimeError("YouTube Music no esta disponible")
        return self._page

    async def _click(self, selectors: list[str]) -> bool:
        page = await self._ensure_page()
        clicked = False
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=1500):
                    await element.click(timeout=3000)
                    await page.wait_for_timeout(300)
                    clicked = True
                    break
            except Exception:
                continue
        await self._focus_foreground_page()
        return clicked

    async def get_state(self) -> PlayerState:
        try:
            page = await self._ensure_page()
            snapshot = await page.evaluate(
                """() => {
                    const bar = document.querySelector('ytmusic-player-bar');
                    const mediaElements = Array.from(document.querySelectorAll('video, audio'));
                    const media =
                        mediaElements.find(element => !element.paused && !element.ended) ||
                        mediaElements.find(element => element.readyState > 0) ||
                        mediaElements[0] ||
                        null;
                    const button = document.querySelector('#play-pause-button');
                    const time = document.querySelector('.time-info')?.textContent || '';
                    return {
                        title: bar?.querySelector('.title')?.textContent?.trim() || null,
                        artist: bar?.querySelector('.subtitle')?.textContent?.trim() || null,
                        thumbnail_url:
                            bar?.querySelector('img.image, #thumbnail img, .thumbnail img, img')?.currentSrc ||
                            bar?.querySelector('img.image, #thumbnail img, .thumbnail img, img')?.src ||
                            null,
                        is_playing: media ? !media.paused && !media.ended : null,
                        button_label: button?.getAttribute('aria-label') || '',
                        position: media ? media.currentTime : null,
                        duration: media && Number.isFinite(media.duration) ? media.duration : null,
                        volume: media ? Math.round(media.volume * 100) : null,
                        time
                    };
                }"""
            )
        except Exception:
            return PlayerState(connected=await self.connect(), is_playing=False, updated_at=utc_now())

        if (
            self._volume is not None
            and snapshot["volume"] is not None
            and snapshot["volume"] != self._volume
        ):
            try:
                await self._apply_volume(page, self._volume)
            except PlaywrightError as exc:
                LOGGER.warning("No se pudo restaurar el volumen fijado: %s", exc)
            else:
                snapshot["volume"] = self._volume

        is_playing = snapshot["is_playing"]
        if is_playing is None:
            label = snapshot["button_label"].lower()
            is_playing = "paus" in label or "pause" in label
        position = snapshot["position"]
        duration = snapshot["duration"]
        if "/" in snapshot["time"]:
            current_time, total_time = [
                value.strip() for value in snapshot["time"].split("/", 1)
            ]
            displayed_position = self._parse_time(current_time)
            displayed_duration = self._parse_time(total_time)
            if displayed_duration > 0:
                position = displayed_position
                duration = displayed_duration
        track = None
        if snapshot["title"]:
            video_id = self._video_id(page.url)
            track = Track(
                id=video_id,
                title=snapshot["title"],
                artists=[snapshot["artist"]] if snapshot["artist"] else [],
                duration_seconds=duration,
                thumbnail_url=snapshot["thumbnail_url"]
                or (
                    f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    if video_id != "unknown"
                    else None
                ),
            )
        return PlayerState(
            connected=True,
            is_playing=is_playing,
            current_track=track,
            position_seconds=position or 0,
            duration_seconds=duration,
            volume=snapshot["volume"] if snapshot["volume"] is not None else self._volume,
            updated_at=utc_now(),
        )

    @staticmethod
    def _parse_time(value: str) -> float:
        try:
            parts = [float(part) for part in value.strip().split(":")]
            return sum(part * (60 ** index) for index, part in enumerate(reversed(parts)))
        except Exception:
            return 0.0

    @staticmethod
    def _video_id(url: str) -> str:
        from urllib.parse import parse_qs
        return parse_qs(urlparse(url).query).get("v", ["unknown"])[0]

    async def play(self) -> PlayerState:
        state = await self.get_state()
        if state.is_playing:
            return state
        if not await self._click(["#play-pause-button"]):
            raise RuntimeError("No se pudo ejecutar Play")
        await asyncio.sleep(0.3)
        return await self.get_state()

    async def pause(self) -> PlayerState:
        state = await self.get_state()
        if not state.is_playing:
            return state
        if not await self._click(["#play-pause-button"]):
            raise RuntimeError("No se pudo ejecutar Pause")
        await asyncio.sleep(0.3)
        return await self.get_state()

    async def next(self) -> PlayerState:
        if not await self._click([".next-button", "#next-button"]):
            raise RuntimeError("No se pudo avanzar al siguiente tema")
        return await self.get_state()

    async def previous(self) -> PlayerState:
        if not await self._click([".previous-button", "#previous-button"]):
            raise RuntimeError("No se pudo volver al tema anterior")
        return await self.get_state()

    async def set_volume(self, volume: int) -> PlayerState:
        volume = max(0, min(100, volume))
        self._volume = volume
        page = await self._ensure_page()
        await self._apply_volume(page, volume)
        state = await self.get_state()
        state.volume = self._volume
        return state

    async def seek(self, position_seconds: float) -> PlayerState:
        if not math.isfinite(position_seconds) or position_seconds < 0:
            raise ValueError("La posicion debe ser un numero finito no negativo")
        page = await self._ensure_page()
        state = await self.get_state()
        if state.duration_seconds is None:
            raise RuntimeError("No se conoce la duracion de la cancion")
        target = min(position_seconds, state.duration_seconds)
        try:
            changed = await page.evaluate(
                """position => {
                    const media = document.querySelector('video, audio');
                    if (!media || !Number.isFinite(media.duration)) return false;
                    media.currentTime = position;
                    return true;
                }""",
                target,
            )
            await page.wait_for_timeout(100)
        except PlaywrightError as exc:
            raise RuntimeError("Fallo al cambiar la posicion de reproduccion") from exc
        if not changed:
            raise RuntimeError("No se pudo cambiar la posicion de reproduccion")
        return await self.get_state()

    async def play_url(self, url: str) -> PlayerState:
        parsed_url = urlparse(url)
        video_ids = parse_qs(parsed_url.query).get("v", [])
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != "music.youtube.com"
            or parsed_url.path != "/watch"
            or not video_ids
        ):
            raise RuntimeError("Solo se pueden reproducir canciones con URL valida de YouTube Music")
        page = await self._ensure_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(1)
            state = await self.play()
            if self._volume is not None:
                await self._apply_volume(page, self._volume)
                state = await self.get_state()
            return state
        finally:
            await self._focus_foreground_page()

    async def _focus_foreground_page(self) -> None:
        if not self._browser or not self.foreground_url:
            return
        foreground_host = urlparse(self.foreground_url).hostname
        for context in self._browser.contexts:
            for page in context.pages:
                if urlparse(page.url).hostname != foreground_host:
                    continue
                try:
                    await page.bring_to_front()
                    try:
                        await self.ensure_fullscreen()
                    except (PlaywrightError, RuntimeError) as exc:
                        LOGGER.warning("No se pudo restaurar pantalla completa: %s", exc)
                    return
                except PlaywrightError as exc:
                    LOGGER.warning("No se pudo enfocar la pestaña de Uptime Kuma: %s", exc)
        if not self._browser.contexts:
            LOGGER.error("No hay un contexto de Chrome para abrir Uptime Kuma")
            return
        try:
            page = await self._browser.contexts[0].new_page()
            await page.goto(self.foreground_url, wait_until="domcontentloaded", timeout=30000)
            await page.bring_to_front()
            try:
                await self.ensure_fullscreen()
            except (PlaywrightError, RuntimeError) as exc:
                LOGGER.warning("No se pudo restaurar pantalla completa: %s", exc)
        except PlaywrightError as exc:
            LOGGER.error("No se pudo restaurar la pestaña de Uptime Kuma: %s", exc)

    @staticmethod
    async def _apply_volume(page: Page, volume: int) -> None:
        await page.evaluate(
            """volume => {
                const slider = document.querySelector('#volume-slider');
                if (slider) {
                    slider.value = volume;
                    slider.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
                    slider.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
                }
                const media = document.querySelector('video, audio');
                if (media) media.volume = volume / 100;
            }""",
            volume,
        )
