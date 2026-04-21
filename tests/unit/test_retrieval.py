from datetime import datetime, timezone
from pathlib import Path

from app.core.config import REPO_ROOT
from app.models.db import count_document_chunks, init_db, upsert_document_snapshot
from app.retrieval.index import build_index, search_index


def test_build_index_is_idempotent_and_search_hits_expected_source(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "retrieval.db"
    clean_root = tmp_path / "data" / "clean"
    raw_root = tmp_path / "data" / "raw"
    snapshot_version = "test-snapshot-v1"

    docs = [
        (
            "snap_install",
            "https://docs.dify.ai/getting-started/install-self-hosted/docker-compose",
            "Docker Compose",
            "Docker Compose\nInstall Dify with Docker Compose for self-hosted deployment.\nSet environment variables before you start containers.\n",
            "install",
        ),
        (
            "snap_api",
            "https://docs.dify.ai/en/use-dify/publish/developing-with-apis",
            "API",
            "API\nUse your Dify app as a backend API service.\nGenerate API credentials and call the API from your backend.\n",
            "api",
        ),
    ]

    for snapshot_id, source_url, title, text, stem in docs:
        raw_path = raw_root / snapshot_version / f"{stem}.html"
        clean_path = clean_root / snapshot_version / f"{stem}.txt"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        clean_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text("<html></html>", encoding="utf-8")
        clean_path.write_text(text, encoding="utf-8")

    monkeypatch.setenv("COPILOT_SQLITE_PATH", str(sqlite_path))
    monkeypatch.setenv("COPILOT_SOURCE_MANIFEST_PATH", str(tmp_path / "data" / "sources.yaml"))
    monkeypatch.setenv("COPILOT_CLEAN_SNAPSHOT_ROOT", str(clean_root))
    monkeypatch.setenv("COPILOT_RAW_SNAPSHOT_ROOT", str(raw_root))

    manifest_path = tmp_path / "data" / "sources.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(
            [
                "product: Dify",
                "authoritative_language: en",
                f"snapshot_version: {snapshot_version}",
                "pages: []",
            ]
        ),
        encoding="utf-8",
    )

    init_db(str(sqlite_path), str(REPO_ROOT / "scripts" / "init_db.sql"))
    for snapshot_id, source_url, title, _, stem in docs:
        upsert_document_snapshot(
            snapshot_id=snapshot_id,
            source_url=source_url,
            fetched_at=datetime.now(timezone.utc),
            content_hash=f"hash-{stem}",
            snapshot_version=snapshot_version,
            title=title,
            stored_path=f"data/raw/{snapshot_version}/{stem}.html",
            sqlite_path=str(sqlite_path),
        )

    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    first_summary = build_index(settings)
    second_summary = build_index(settings)

    assert first_summary.processed_clean_files == 2
    assert second_summary.chunk_count == first_summary.chunk_count
    assert count_document_chunks(snapshot_version, sqlite_path=str(sqlite_path)) == first_summary.chunk_count

    backend, results = search_index(
        query="backend api service",
        top_k=3,
        sqlite_path=str(sqlite_path),
        snapshot_version=snapshot_version,
    )

    assert backend in {"sqlite-fts5", "lexical-fallback"}
    assert results
    assert results[0].source_url == "https://docs.dify.ai/en/use-dify/publish/developing-with-apis"
