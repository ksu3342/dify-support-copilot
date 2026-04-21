from fastapi.testclient import TestClient


def test_healthz_returns_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_SQLITE_PATH", str(tmp_path / "test.db"))

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.api.main import app

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["check_type"] == "liveness"
    assert response.json()["sqlite_accessible"] is True
