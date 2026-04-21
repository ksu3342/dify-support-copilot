import hashlib
import sqlite3
from pathlib import Path

import httpx
import pytest

from app.core.config import REPO_ROOT, Settings
from app.ingest.fetch import SnapshotConflictError, _fetch_single_page, build_snapshot_paths
from app.models.db import get_document_snapshot_by_requested_url, init_db
from app.retrieval.index import _derive_clean_path


def test_init_db_migrates_legacy_document_snapshots_table(tmp_path):
    sqlite_path = tmp_path / "legacy.db"
    requested_url = "https://docs.dify.ai/en/self-host/troubleshooting/common-issues"

    with sqlite3.connect(sqlite_path) as connection:
        connection.executescript(
            """
            CREATE TABLE document_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                source_url TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                snapshot_version TEXT NOT NULL,
                title TEXT,
                stored_path TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO document_snapshots (
                snapshot_id,
                source_url,
                fetched_at,
                content_hash,
                snapshot_version,
                title,
                stored_path,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "snap_legacy",
                requested_url,
                "2026-04-21T00:00:00+00:00",
                "legacy-hash",
                "legacy-snapshot-v1",
                "Legacy Snapshot",
                "data/raw/legacy-snapshot-v1/common-issues.html",
                "2026-04-21T00:00:00+00:00",
            ),
        )
        connection.commit()

    init_db(str(sqlite_path), str(REPO_ROOT / "scripts" / "init_db.sql"))

    with sqlite3.connect(sqlite_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(document_snapshots)").fetchall()
        }
        row = connection.execute(
            """
            SELECT source_url, requested_url, final_url
            FROM document_snapshots
            WHERE snapshot_id = 'snap_legacy'
            """
        ).fetchone()

    assert {"requested_url", "final_url"}.issubset(columns)
    assert row == (requested_url, requested_url, requested_url)


def test_fetch_single_page_uses_configured_snapshot_roots_and_rejects_drift(tmp_path):
    requested_url = "https://docs.dify.ai/en/self-host/troubleshooting/common-issues"
    snapshot_version = "snapshot-test-v1"
    html_state = {
        "value": "<html><head><title>Common Issues</title></head><body><main><h1>Common Issues</h1><p>Check docker logs before restarting the service.</p></main></body></html>"
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html_state["value"], request=request)

    settings = Settings(
        sqlite_path=str(tmp_path / "copilot.db"),
        sqlite_init_script=str(REPO_ROOT / "scripts" / "init_db.sql"),
        source_manifest_path=str(tmp_path / "sources.yaml"),
        raw_snapshot_root=str(tmp_path / "custom-storage" / "raw"),
        clean_snapshot_root=str(tmp_path / "custom-storage" / "clean"),
    )
    init_db(settings.sqlite_path, settings.sqlite_init_script)

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        first = _fetch_single_page(
            client=client,
            settings=settings,
            snapshot_version=snapshot_version,
            source_url=requested_url,
        )
        second = _fetch_single_page(
            client=client,
            settings=settings,
            snapshot_version=snapshot_version,
            source_url=requested_url,
        )

        html_state["value"] = "<html><head><title>Common Issues</title></head><body><main><h1>Common Issues</h1><p>The page content changed and should conflict.</p></main></body></html>"
        with pytest.raises(SnapshotConflictError):
            _fetch_single_page(
                client=client,
                settings=settings,
                snapshot_version=snapshot_version,
                source_url=requested_url,
            )

    stored = get_document_snapshot_by_requested_url(
        requested_url=requested_url,
        snapshot_version=snapshot_version,
        sqlite_path=settings.sqlite_path,
    )
    expected_paths = build_snapshot_paths(
        raw_snapshot_root=Path(settings.raw_snapshot_root),
        clean_snapshot_root=Path(settings.clean_snapshot_root),
        snapshot_version=snapshot_version,
        source_url=requested_url,
    )
    repo_default_raw_path = REPO_ROOT / first.raw_path
    repo_default_clean_path = REPO_ROOT / first.clean_path
    derived_clean_path = _derive_clean_path(Path(settings.clean_snapshot_root), stored.stored_path)

    assert first.success is True
    assert second.success is True
    assert stored is not None
    assert stored.final_url == requested_url
    assert stored.stored_path == first.raw_path.as_posix()
    assert stored.content_hash == hashlib.sha256(
        "<html><head><title>Common Issues</title></head><body><main><h1>Common Issues</h1><p>Check docker logs before restarting the service.</p></main></body></html>".encode(
            "utf-8"
        )
    ).hexdigest()
    assert expected_paths.raw_absolute_path.read_text(encoding="utf-8").startswith("<html><head><title>Common Issues</title>")
    assert expected_paths.clean_absolute_path.exists()
    assert derived_clean_path == expected_paths.clean_absolute_path
    assert derived_clean_path.read_text(encoding="utf-8").startswith("Common Issues")
    assert not repo_default_raw_path.exists()
    assert not repo_default_clean_path.exists()
