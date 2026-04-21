import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT
from app.models.db import init_db


FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"
SUPPORT_MANIFEST_PATH = FIXTURES_ROOT / "support_sources.yaml"
SUPPORT_SEED_PATH = FIXTURES_ROOT / "support_seed.json"


def _seed_support_documents(sqlite_path: Path) -> None:
    payload = json.loads(SUPPORT_SEED_PATH.read_text(encoding="utf-8"))
    snapshot_version = payload["snapshot_version"]
    fetched_at = payload["fetched_at"]
    created_at = payload["created_at"]

    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute("DELETE FROM support_runs")
        connection.execute("DELETE FROM retrieval_hits")
        connection.execute("DELETE FROM tickets")
        connection.execute("DELETE FROM document_chunks")
        connection.execute("DELETE FROM document_snapshots")

        fts_available = True
        try:
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts
                USING fts5(
                    chunk_id UNINDEXED,
                    title,
                    content,
                    tokenize = 'unicode61'
                )
                """
            )
            connection.execute("DELETE FROM document_chunks_fts")
        except sqlite3.OperationalError:
            fts_available = False

        for document in payload["documents"]:
            content_hash = hashlib.sha256(
                "\n".join(chunk["content"] for chunk in document["chunk_records"]).encode("utf-8")
            ).hexdigest()
            connection.execute(
                """
                INSERT INTO document_snapshots (
                    snapshot_id,
                    source_url,
                    requested_url,
                    final_url,
                    fetched_at,
                    content_hash,
                    snapshot_version,
                    title,
                    stored_path,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document["snapshot_id"],
                    document["source_url"],
                    document["source_url"],
                    document["source_url"],
                    fetched_at,
                    content_hash,
                    snapshot_version,
                    document["title"],
                    document["stored_path"],
                    created_at,
                ),
            )

            for chunk in document["chunk_records"]:
                connection.execute(
                    """
                    INSERT INTO document_chunks (
                        chunk_id,
                        snapshot_id,
                        source_url,
                        snapshot_version,
                        title,
                        chunk_index,
                        content,
                        char_count,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk["chunk_id"],
                        document["snapshot_id"],
                        document["source_url"],
                        snapshot_version,
                        document["title"],
                        chunk["chunk_index"],
                        chunk["content"],
                        len(chunk["content"]),
                        created_at,
                        created_at,
                    ),
                )

                if fts_available:
                    connection.execute(
                        """
                        INSERT INTO document_chunks_fts (chunk_id, title, content)
                        VALUES (?, ?, ?)
                        """,
                        (chunk["chunk_id"], document["title"], chunk["content"]),
                    )

        connection.commit()
    finally:
        connection.close()


def _clear_runtime_caches() -> None:
    from app.core.config import get_settings
    from app.support.service import _load_manifest

    get_settings.cache_clear()
    _load_manifest.cache_clear()


def _build_client(monkeypatch, sqlite_path: Path, seed_documents: bool):
    monkeypatch.setenv("COPILOT_SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("COPILOT_SOURCE_MANIFEST_PATH", str(SUPPORT_MANIFEST_PATH))

    _clear_runtime_caches()

    from app.core.config import get_settings

    settings = get_settings()
    init_db(settings.sqlite_path, settings.sqlite_init_script)
    if seed_documents:
        _seed_support_documents(sqlite_path)

    from app.api.main import app

    return TestClient(app)


@pytest.fixture
def support_client(tmp_path, monkeypatch):
    target_db = tmp_path / "copilot.db"

    with _build_client(monkeypatch=monkeypatch, sqlite_path=target_db, seed_documents=True) as client:
        yield client, target_db

    _clear_runtime_caches()


@pytest.fixture
def unready_support_client(tmp_path, monkeypatch):
    target_db = tmp_path / "copilot.db"

    with _build_client(monkeypatch=monkeypatch, sqlite_path=target_db, seed_documents=False) as client:
        yield client, target_db

    _clear_runtime_caches()
