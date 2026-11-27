import asyncio
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.chrome_playwright import ChromePlaywrightAdapter
from app.api.routes_settings import build_settings_router
from app.services.main_tab_settings import MainTabSettingsService


def test_main_tab_url_persists_between_service_instances(tmp_path):
    database_path = tmp_path / "settings.db"
    first = MainTabSettingsService(database_path)
    first.set_main_tab_url("https://status.example.org/status/all")

    restarted = MainTabSettingsService(database_path)

    assert restarted.get_main_tab_url("https://example.com/") == (
        "https://status.example.org/status/all"
    )


def test_settings_api_saves_and_applies_main_tab_url(tmp_path):
    settings_service = MainTabSettingsService(tmp_path / "settings.db")
    browser = Mock()
    browser.set_foreground_url = AsyncMock(return_value=True)
    chrome_startup = Mock()
    chrome_startup.startup_urls = ["https://example.com/", "https://music.youtube.com/"]
    app = FastAPI()
    app.include_router(
        build_settings_router(
            settings_service,
            browser,
            chrome_startup,
            "https://example.com/",
            "https://music.youtube.com/",
            "test-token",
        )
    )

    with TestClient(app) as client:
        unauthorized = client.get("/api/settings")
        response = client.put(
            "/api/settings/main-tab",
            headers={"Authorization": "Bearer test-token"},
            json={"url": "https://status.example.org/status/all"},
        )
        current = client.get(
            "/api/settings",
            headers={"Authorization": "Bearer test-token"},
        )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json() == {
        "main_tab_url": "https://status.example.org/status/all",
        "applied": True,
    }
    assert current.json()["main_tab_url"] == "https://status.example.org/status/all"
    assert chrome_startup.startup_urls[0] == "https://status.example.org/status/all"
    browser.set_foreground_url.assert_awaited_once_with(
        "https://status.example.org/status/all"
    )


def test_settings_api_rejects_youtube_music_as_main_tab(tmp_path):
    settings_service = MainTabSettingsService(tmp_path / "settings.db")
    browser = Mock()
    browser.set_foreground_url = AsyncMock()
    chrome_startup = Mock(startup_urls=["https://example.com/"])
    app = FastAPI()
    app.include_router(
        build_settings_router(
            settings_service,
            browser,
            chrome_startup,
            "https://example.com/",
            "https://music.youtube.com/",
            "test-token",
        )
    )

    with TestClient(app) as client:
        response = client.put(
            "/api/settings/main-tab",
            headers={"Authorization": "Bearer test-token"},
            json={"url": "https://music.youtube.com/"},
        )

    assert response.status_code == 422
    browser.set_foreground_url.assert_not_awaited()
    assert settings_service.get_main_tab_url("https://example.com/") == "https://example.com/"


def test_chrome_updates_existing_primary_tab(tmp_path):
    adapter = ChromePlaywrightAdapter(
        "http://127.0.0.1:9222",
        "https://music.youtube.com/",
        foreground_url="https://example.com/",
    )
    page = Mock(url="https://example.com/")
    page.goto = AsyncMock()
    page.bring_to_front = AsyncMock()
    context = Mock(pages=[page])
    adapter._browser = Mock(contexts=[context])
    adapter.ensure_fullscreen = AsyncMock()

    applied = asyncio.run(
        adapter.set_foreground_url("https://status.example.org/status/all")
    )

    assert applied is True
    assert adapter.foreground_url == "https://status.example.org/status/all"
    page.goto.assert_awaited_once_with(
        "https://status.example.org/status/all",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    page.bring_to_front.assert_awaited_once()
    adapter.ensure_fullscreen.assert_awaited_once()
