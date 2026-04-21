from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from app.core.config import Settings
from app.ingest.fetch import load_source_manifest


FETCH_COMMAND = r".\.venv\Scripts\python scripts\fetch_sources.py"
BUILD_COMMAND = r".\.venv\Scripts\python scripts\build_index.py"


@dataclass(frozen=True)
class SupportReadinessStatus:
    ready: bool
    snapshot_version: str
    snapshot_count: int
    chunk_count: int
    reasons: List[str] = field(default_factory=list)


class SupportReadinessError(RuntimeError):
    pass


def check_support_readiness(settings: Settings) -> SupportReadinessStatus:
    snapshot_version = "unknown"
    reasons: List[str] = []

    try:
        manifest = load_source_manifest(Path(settings.source_manifest_path))
        snapshot_version = manifest.snapshot_version
    except Exception as exc:
        reasons.append(f"Source manifest could not be loaded: {exc}.")
        return SupportReadinessStatus(
            ready=False,
            snapshot_version=snapshot_version,
            snapshot_count=0,
            chunk_count=0,
            reasons=reasons,
        )

    sqlite_path = Path(settings.sqlite_path)
    if not sqlite_path.exists():
        reasons.append(f"SQLite database '{sqlite_path}' does not exist.")
        return SupportReadinessStatus(
            ready=False,
            snapshot_version=snapshot_version,
            snapshot_count=0,
            chunk_count=0,
            reasons=reasons,
        )

    try:
        with sqlite3.connect(sqlite_path) as connection:
            missing_tables = [
                table_name
                for table_name in ("document_snapshots", "document_chunks")
                if not _table_exists(connection, table_name)
            ]
            if missing_tables:
                reasons.append(
                    "Required SQLite tables are missing: " + ", ".join(missing_tables) + "."
                )
                return SupportReadinessStatus(
                    ready=False,
                    snapshot_version=snapshot_version,
                    snapshot_count=0,
                    chunk_count=0,
                    reasons=reasons,
                )

            snapshot_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM document_snapshots
                    WHERE snapshot_version = ?
                    """,
                    (snapshot_version,),
                ).fetchone()[0]
            )
            chunk_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM document_chunks
                    WHERE snapshot_version = ?
                    """,
                    (snapshot_version,),
                ).fetchone()[0]
            )
    except sqlite3.Error as exc:
        reasons.append(
            "SQLite could not be inspected safely. "
            f"Underlying SQLite error class: {exc.__class__.__name__}."
        )
        return SupportReadinessStatus(
            ready=False,
            snapshot_version=snapshot_version,
            snapshot_count=0,
            chunk_count=0,
            reasons=reasons,
        )

    if snapshot_count <= 0:
        reasons.append(
            f"No document_snapshots were found for snapshot_version='{snapshot_version}'."
        )
    if chunk_count <= 0:
        reasons.append(
            f"No document_chunks were found for snapshot_version='{snapshot_version}'."
        )

    return SupportReadinessStatus(
        ready=not reasons,
        snapshot_version=snapshot_version,
        snapshot_count=snapshot_count,
        chunk_count=chunk_count,
        reasons=reasons,
    )


def require_support_readiness(settings: Settings) -> SupportReadinessStatus:
    readiness = check_support_readiness(settings)
    if readiness.ready:
        return readiness
    raise SupportReadinessError(_format_not_ready_message(readiness))


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _format_not_ready_message(readiness: SupportReadinessStatus) -> str:
    reasons = " ".join(readiness.reasons) if readiness.reasons else "Support baseline is not ready."
    return (
        "Support baseline is not ready to answer questions. "
        f"snapshot_version='{readiness.snapshot_version}', "
        f"snapshot_count={readiness.snapshot_count}, "
        f"chunk_count={readiness.chunk_count}. "
        f"{reasons} Run '{FETCH_COMMAND}' and '{BUILD_COMMAND}' first."
    )
