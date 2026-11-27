import asyncio

import pytest

from app.services.chrome_startup import ChromeStartup
from app.adapters.chrome_playwright import ChromePlaywrightAdapter


def test_build_command_uses_dedicated_profile_and_both_pages(tmp_path):
    startup = ChromeStartup(
        cdp_url="http://127.0.0.1:9222",
        user_data_dir=tmp_path / "chrome-profile",
        startup_urls=[
            "https://example.com/status/all",
            "https://music.youtube.com/",
        ],
        executable="chrome.exe",
    )

    command = startup.build_command("chrome.exe")

    assert command[0] == "chrome.exe"
    assert "--remote-debugging-address=127.0.0.1" in command
    assert "--remote-debugging-port=9222" in command
    assert "--start-fullscreen" in command
    assert any("chrome-profile" in argument for argument in command)
    assert command[-2:] == [
        "https://example.com/status/all",
        "https://music.youtube.com/",
    ]


def test_existing_cdp_instance_is_reused(monkeypatch, tmp_path):
    startup = ChromeStartup(
        cdp_url="http://127.0.0.1:9222",
        user_data_dir=tmp_path / "chrome-profile",
        startup_urls=[],
        probe=lambda: True,
    )

    def unexpected_launch(*args, **kwargs):
        raise AssertionError(f"Unexpected Chrome launch: {args}, {kwargs}")

    monkeypatch.setattr("app.services.chrome_startup.subprocess.Popen", unexpected_launch)
    assert asyncio.run(startup.ensure_running()) is False


def test_cdp_url_cannot_bind_to_lan_host(tmp_path):
    with pytest.raises(ValueError, match="loopback"):
        ChromeStartup(
            cdp_url="http://192.168.1.10:9222",
            user_data_dir=tmp_path / "chrome-profile",
            startup_urls=[],
        )


def test_redirected_music_homepage_is_not_opened_twice():
    assert ChromePlaywrightAdapter._same_startup_page(
        "https://music.youtube.com/browse",
        "https://music.youtube.com/",
    )
