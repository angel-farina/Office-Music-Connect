import os

os.environ.setdefault("APP_ACCESS_TOKEN", "test-token")

from fastapi.testclient import TestClient

from app.main import app


def test_player_requires_auth():
    with TestClient(app) as client:
        response = client.post("/api/player/play")
    assert response.status_code in (401, 403)


def test_player_rejects_wrong_token():
    with TestClient(app) as client:
        response = client.post(
            "/api/player/play",
            headers={"Authorization": "Bearer wrong-token"},
        )
    assert response.status_code == 401
