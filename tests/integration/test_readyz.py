import sqlite3

from fastapi.testclient import TestClient


def test_readyz_returns_ready_true_for_seeded_support_baseline(support_client):
    client, _ = support_client

    response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["snapshot_version"]
    assert payload["snapshot_count"] > 0
    assert payload["chunk_count"] > 0
    assert payload["reasons"] == []


def test_readyz_returns_not_ready_for_empty_support_baseline(unready_support_client):
    client, _ = unready_support_client

    response = client.get("/readyz")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ready"] is False
    assert payload["snapshot_count"] == 0
    assert payload["chunk_count"] == 0
    assert any("document_snapshots" in reason for reason in payload["reasons"])
    assert any("document_chunks" in reason for reason in payload["reasons"])


def test_readyz_returns_not_ready_when_required_tables_are_missing(tmp_path, monkeypatch):
    target_db = tmp_path / "missing-tables.db"
    sqlite3.connect(target_db).close()

    monkeypatch.setenv("COPILOT_SQLITE_PATH", str(target_db))
    monkeypatch.setenv(
        "COPILOT_SOURCE_MANIFEST_PATH",
        str(r"D:\AI agent\dify-support-copilot\tests\fixtures\support_sources.yaml"),
    )

    from app.api import main as main_module
    from app.core.config import get_settings
    from app.support.service import _load_manifest

    get_settings.cache_clear()
    _load_manifest.cache_clear()
    monkeypatch.setattr(main_module, "init_db", lambda *args, **kwargs: None)

    with TestClient(main_module.app) as client:
        response = client.get("/readyz")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ready"] is False
    assert payload["snapshot_count"] == 0
    assert payload["chunk_count"] == 0
    assert any("document_snapshots" in reason for reason in payload["reasons"])
    assert any("document_chunks" in reason for reason in payload["reasons"])

    get_settings.cache_clear()
    _load_manifest.cache_clear()


def test_support_ask_returns_503_when_support_baseline_is_not_ready(unready_support_client, monkeypatch):
    client, _ = unready_support_client
    from app.support import service as support_service

    def _unexpected_search(*args, **kwargs):
        raise AssertionError("search_index should not be called when readiness fails")

    monkeypatch.setattr(support_service, "search_index", _unexpected_search)

    response = client.post(
        "/v1/support/ask",
        json={"question": "How do I configure chunk settings for a knowledge base in Dify?"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert "Support baseline is not ready to answer questions." in payload["detail"]
    assert "scripts\\fetch_sources.py" in payload["detail"]
    assert "scripts\\build_index.py" in payload["detail"]
