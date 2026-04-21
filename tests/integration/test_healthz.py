import sqlite3

from fastapi.testclient import TestClient


def test_healthz_returns_sqlite_accessible_false_without_creating_missing_db(tmp_path, monkeypatch):
    target_db = tmp_path / "missing" / "test.db"
    monkeypatch.setenv("COPILOT_SQLITE_PATH", str(target_db))

    from app.api import main as main_module
    from app.core.config import get_settings
    from app.support.service import _load_manifest

    get_settings.cache_clear()
    _load_manifest.cache_clear()
    monkeypatch.setattr(main_module, "init_db", lambda *args, **kwargs: None)

    with TestClient(main_module.app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["check_type"] == "liveness"
    assert payload["sqlite_accessible"] is False
    assert not target_db.exists()

    get_settings.cache_clear()
    _load_manifest.cache_clear()


def test_healthz_returns_sqlite_accessible_true_for_existing_db(tmp_path, monkeypatch):
    target_db = tmp_path / "existing.db"
    sqlite3.connect(target_db).close()
    monkeypatch.setenv("COPILOT_SQLITE_PATH", str(target_db))

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.api.main import app

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["check_type"] == "liveness"
    assert payload["sqlite_accessible"] is True
