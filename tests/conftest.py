import os
from unittest.mock import AsyncMock

import pytest


os.environ.setdefault("APP_ACCESS_TOKEN", "test-token")
os.environ.setdefault("CHROME_AUTO_LAUNCH", "false")


@pytest.fixture(autouse=True)
def avoid_starting_real_chrome(monkeypatch):
    from app.main import player

    monkeypatch.setattr(player, "start", AsyncMock())
    monkeypatch.setattr(player, "stop", AsyncMock())
