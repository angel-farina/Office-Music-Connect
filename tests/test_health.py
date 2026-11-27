import os

os.environ.setdefault("APP_ACCESS_TOKEN", "test-token")

from fastapi.testclient import TestClient

from app.main import app


def test_health_does_not_require_auth():
    with TestClient(app) as client:
        response = client.get("/api/health")
        page = client.get("/")
        favicon = client.get("/static/favicon.svg")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "Office Music Connect"
    assert 'href="/static/favicon.svg"' in page.text
    assert '@angel-farina</a>' in page.text
    assert favicon.status_code == 200
    assert "<svg" in favicon.text
