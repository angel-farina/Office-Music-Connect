import asyncio
from unittest.mock import AsyncMock, Mock

from app.adapters.chrome_playwright import ChromePlaywrightAdapter
from app.models.player import PlayerState, utc_now


def test_player_state_reads_media_playing_and_volume():
    adapter = ChromePlaywrightAdapter("http://127.0.0.1:9222", "https://music.youtube.com/")
    page = Mock()
    page.url = "https://music.youtube.com/watch?v=track-id"
    page.evaluate = AsyncMock(
        return_value={
            "title": "Cancion",
            "artist": "Artista",
            "thumbnail_url": "https://example.com/cover.jpg",
            "is_playing": True,
            "track_ended": False,
            "button_label": "Pausar",
            "position": 15.0,
            "duration": 180.0,
            "volume": 24,
            "time": "",
        }
    )
    adapter._ensure_page = AsyncMock(return_value=page)

    state = asyncio.run(adapter.get_state())

    assert state.is_playing is True
    assert state.volume == 24
    assert state.current_track is not None
    assert state.current_track.title == "Cancion"
    assert state.current_track.thumbnail_url == "https://example.com/cover.jpg"


def test_player_state_builds_thumbnail_fallback_from_video_id():
    adapter = ChromePlaywrightAdapter("http://127.0.0.1:9222", "https://music.youtube.com/")
    page = Mock()
    page.url = "https://music.youtube.com/watch?v=track-id"
    page.evaluate = AsyncMock(
        return_value={
            "title": "Cancion",
            "artist": None,
            "thumbnail_url": None,
            "is_playing": False,
            "track_ended": False,
            "button_label": "Reproducir",
            "position": 0.0,
            "duration": 120.0,
            "volume": 50,
            "time": "",
        }
    )
    adapter._ensure_page = AsyncMock(return_value=page)

    state = asyncio.run(adapter.get_state())

    assert state.current_track is not None
    assert state.current_track.thumbnail_url == "https://i.ytimg.com/vi/track-id/hqdefault.jpg"


def test_player_state_prefers_visible_track_time_over_stale_media_clock():
    adapter = ChromePlaywrightAdapter("http://127.0.0.1:9222", "https://music.youtube.com/")
    page = Mock()
    page.url = "https://music.youtube.com/watch?v=new-track"
    page.evaluate = AsyncMock(
        return_value={
            "title": "Cancion nueva",
            "artist": None,
            "thumbnail_url": None,
            "is_playing": True,
            "button_label": "Pausar",
            "position": 184.0,
            "duration": 240.0,
            "volume": 50,
            "time": "0:03 / 3:20",
        }
    )
    adapter._ensure_page = AsyncMock(return_value=page)

    state = asyncio.run(adapter.get_state())

    assert state.position_seconds == 3
    assert state.duration_seconds == 200


def test_play_is_idempotent_when_track_is_already_playing():
    adapter = ChromePlaywrightAdapter("http://127.0.0.1:9222", "https://music.youtube.com/")
    adapter.get_state = AsyncMock(
        return_value=PlayerState(connected=True, is_playing=True, updated_at=utc_now())
    )
    adapter._click = AsyncMock(return_value=True)

    state = asyncio.run(adapter.play())

    assert state.is_playing is True
    adapter._click.assert_not_awaited()


def test_play_url_preserves_volume_and_restores_uptime_tab():
    adapter = ChromePlaywrightAdapter("http://127.0.0.1:9222", "https://music.youtube.com/")
    music_page = Mock()
    music_page.goto = AsyncMock()
    adapter._ensure_page = AsyncMock(return_value=music_page)
    adapter._focus_foreground_page = AsyncMock()
    adapter._volume = 24
    adapter._apply_volume = AsyncMock()
    state = PlayerState(connected=True, is_playing=True, updated_at=utc_now())
    adapter.play = AsyncMock(return_value=state)
    adapter.get_state = AsyncMock(return_value=state)

    result = asyncio.run(adapter.play_url("https://music.youtube.com/watch?v=track-id"))

    assert result.is_playing is True
    adapter._apply_volume.assert_awaited_once_with(music_page, 24)
    adapter._focus_foreground_page.assert_awaited_once()


def test_focuses_uptime_tab():
    adapter = ChromePlaywrightAdapter(
        "http://127.0.0.1:9222",
        "https://music.youtube.com/",
        foreground_url="https://example.com/status/all",
    )
    uptime_page = Mock()
    uptime_page.url = "https://example.com/status/all"
    uptime_page.bring_to_front = AsyncMock()
    music_page = Mock()
    music_page.url = "https://music.youtube.com/"
    adapter._browser = Mock(contexts=[Mock(pages=[music_page, uptime_page])])
    adapter.ensure_fullscreen = AsyncMock()

    asyncio.run(adapter._focus_foreground_page())

    uptime_page.bring_to_front.assert_awaited_once()
    adapter.ensure_fullscreen.assert_awaited_once()


def test_fullscreen_uses_chrome_window_bounds():
    adapter = ChromePlaywrightAdapter("http://127.0.0.1:9222", "https://music.youtube.com/")
    session = Mock()
    session.send = AsyncMock(side_effect=[{"windowId": 12}, {}])
    session.detach = AsyncMock()
    browser = Mock()
    browser.new_browser_cdp_session = AsyncMock(return_value=session)
    adapter._browser = browser

    asyncio.run(adapter.ensure_fullscreen())

    session.send.assert_any_await("Browser.setWindowBounds", {
        "windowId": 12,
        "bounds": {"windowState": "fullscreen"},
    })
    session.detach.assert_awaited_once()


def test_seek_clamps_target_to_track_duration():
    adapter = ChromePlaywrightAdapter("http://127.0.0.1:9222", "https://music.youtube.com/")
    page = Mock()
    page.evaluate = AsyncMock(return_value=True)
    page.wait_for_timeout = AsyncMock()
    adapter._ensure_page = AsyncMock(return_value=page)
    adapter.get_state = AsyncMock(
        side_effect=[
            PlayerState(
                connected=True,
                position_seconds=15,
                duration_seconds=100,
                updated_at=utc_now(),
            ),
            PlayerState(
                connected=True,
                position_seconds=100,
                duration_seconds=100,
                updated_at=utc_now(),
            ),
        ]
    )

    state = asyncio.run(adapter.seek(150))

    assert page.evaluate.await_args.args[1] == 100
    assert state.position_seconds == 100


def test_play_url_rejects_non_youtube_music_urls():
    adapter = ChromePlaywrightAdapter("http://127.0.0.1:9222", "https://music.youtube.com/")

    try:
        asyncio.run(adapter.play_url("https://example.com/watch?v=not-music"))
    except RuntimeError as exc:
        assert "YouTube Music" in str(exc)
    else:
        raise AssertionError("Se esperaba rechazar una URL externa")
