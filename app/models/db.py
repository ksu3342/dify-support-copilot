import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from app.models.api import Category, RunRecord, RunStatus, SnapshotRecord, TicketRecord, TicketStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_parent_dir(sqlite_path: str) -> None:
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)


def _serialize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _connect(sqlite_path: str) -> sqlite3.Connection:
    _ensure_parent_dir(sqlite_path)
    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(sqlite_path: str, init_script_path: str) -> None:
    script = Path(init_script_path).read_text(encoding="utf-8")
    with _connect(sqlite_path) as connection:
        connection.executescript(script)
        connection.commit()


def insert_support_run(
    question: str,
    request_payload: Dict[str, Any],
    category: Category,
    confidence: float,
    status: RunStatus,
    sqlite_path: Optional[str] = None,
) -> RunRecord:
    target_db = sqlite_path or _default_sqlite_path()
    now = _utc_now().isoformat()
    run_id = str(uuid4())
    payload = json.dumps(request_payload, ensure_ascii=True)
    with _connect(target_db) as connection:
        connection.execute(
            """
            INSERT INTO support_runs (
                run_id,
                question,
                request_payload,
                status,
                category,
                confidence,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, question, payload, status.value, category.value, confidence, now, now),
        )
        connection.commit()
    return get_support_run(run_id, sqlite_path=target_db)  # type: ignore[return-value]


def get_support_run(run_id: str, sqlite_path: Optional[str] = None) -> Optional[RunRecord]:
    target_db = sqlite_path or _default_sqlite_path()
    with _connect(target_db) as connection:
        row = connection.execute(
            """
            SELECT run_id, question, status, category, confidence, created_at, updated_at
            FROM support_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return RunRecord(
        run_id=row["run_id"],
        question=row["question"],
        status=RunStatus(row["status"]),
        category=Category(row["category"]),
        confidence=float(row["confidence"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def get_ticket(ticket_id: str, sqlite_path: Optional[str] = None) -> Optional[TicketRecord]:
    target_db = sqlite_path or _default_sqlite_path()
    with _connect(target_db) as connection:
        row = connection.execute(
            """
            SELECT ticket_id, run_id, status, summary, created_at, updated_at
            FROM tickets
            WHERE ticket_id = ?
            """,
            (ticket_id,),
        ).fetchone()
    if row is None:
        return None
    return TicketRecord(
        ticket_id=row["ticket_id"],
        run_id=row["run_id"],
        status=TicketStatus(row["status"]),
        summary=row["summary"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def upsert_document_snapshot(
    snapshot_id: str,
    source_url: str,
    fetched_at: datetime,
    content_hash: str,
    snapshot_version: str,
    title: Optional[str],
    stored_path: str,
    created_at: Optional[datetime] = None,
    sqlite_path: Optional[str] = None,
) -> SnapshotRecord:
    target_db = sqlite_path or _default_sqlite_path()
    created_at_value = _serialize_datetime(created_at or _utc_now())
    fetched_at_value = _serialize_datetime(fetched_at)
    with _connect(target_db) as connection:
        existing = connection.execute(
            """
            SELECT created_at
            FROM document_snapshots
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchone()
        effective_created_at = existing["created_at"] if existing is not None else created_at_value
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
            ON CONFLICT(snapshot_id) DO UPDATE SET
                source_url = excluded.source_url,
                fetched_at = excluded.fetched_at,
                content_hash = excluded.content_hash,
                snapshot_version = excluded.snapshot_version,
                title = excluded.title,
                stored_path = excluded.stored_path
            """,
            (
                snapshot_id,
                source_url,
                fetched_at_value,
                content_hash,
                snapshot_version,
                title,
                stored_path,
                effective_created_at,
            ),
        )
        connection.commit()
    return get_document_snapshot(snapshot_id, sqlite_path=target_db)  # type: ignore[return-value]


def get_document_snapshot(snapshot_id: str, sqlite_path: Optional[str] = None) -> Optional[SnapshotRecord]:
    target_db = sqlite_path or _default_sqlite_path()
    with _connect(target_db) as connection:
        row = connection.execute(
            """
            SELECT snapshot_id, source_url, fetched_at, content_hash, snapshot_version, title, stored_path, created_at
            FROM document_snapshots
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchone()
    if row is None:
        return None
    return SnapshotRecord(
        snapshot_id=row["snapshot_id"],
        source_url=row["source_url"],
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        content_hash=row["content_hash"],
        snapshot_version=row["snapshot_version"],
        title=row["title"],
        stored_path=row["stored_path"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )


def count_document_snapshots(snapshot_version: Optional[str] = None, sqlite_path: Optional[str] = None) -> int:
    target_db = sqlite_path or _default_sqlite_path()
    query = "SELECT COUNT(*) AS total FROM document_snapshots"
    parameters: tuple[str, ...] = ()
    if snapshot_version is not None:
        query += " WHERE snapshot_version = ?"
        parameters = (snapshot_version,)
    with _connect(target_db) as connection:
        row = connection.execute(query, parameters).fetchone()
    return int(row["total"]) if row is not None else 0


def _default_sqlite_path() -> str:
    from app.core.config import get_settings

    return get_settings().sqlite_path
