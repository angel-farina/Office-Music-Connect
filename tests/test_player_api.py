import os
from unittest.mock import AsyncMock

os.environ.setdefault("APP_ACCESS_TOKEN", "test-token")

from fastapi.testclient import TestClient

from app.main import app, player, queue
from app.models.player import PlayerState, utc_now


def test_volume_validation():
    with TestClient(app) as client:
        response = client.post(
            "/api/player/volume",
            headers={"Authorization": "Bearer test-token"},
            json={"volume": 101},
        )
    assert response.status_code == 422


def test_seek_rejects_negative_position():
    with TestClient(app) as client:
        response = client.post(
            "/api/player/seek",
            headers={"Authorization": "Bearer test-token"},
            json={"position_seconds": -1},
        )
    assert response.status_code == 422


def test_play_now_does_not_add_track_to_queue(monkeypatch):
    track_url = "https://music.youtube.com/watch?v=immediate-track"
    queue_add = AsyncMock()
    play_url = AsyncMock(
        return_value=PlayerState(
            connected=True,
            is_playing=True,
            updated_at=utc_now(),
        )
    )
    monkeypatch.setattr(queue, "add", queue_add)
    monkeypatch.setattr(
        player,
        "play_url",
        play_url,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/queue",
            headers={"Authorization": "Bearer test-token"},
            json={
                "track": {
                    "id": "immediate-track",
                    "title": "Inmediata",
                    "watch_url": track_url,
                },
                "play_now": True,
            },
        )

    assert response.status_code == 200
    queue_add.assert_not_awaited()
    play_url.assert_awaited_once_with(track_url)
