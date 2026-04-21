import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.models.api import Category, RunRecord, RunStatus, SnapshotRecord, TicketRecord, TicketStatus


@dataclass(frozen=True)
class StoredSupportRun:
    run_id: str
    question: str
    request_payload: Dict[str, Any]
    status: RunStatus
    category: Category
    confidence: float
    created_at: datetime
    updated_at: datetime


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
        _apply_migrations(connection)
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


def get_support_run_state(run_id: str, sqlite_path: Optional[str] = None) -> Optional[StoredSupportRun]:
    target_db = sqlite_path or _default_sqlite_path()
    with _connect(target_db) as connection:
        row = connection.execute(
            """
            SELECT run_id, question, request_payload, status, category, confidence, created_at, updated_at
            FROM support_runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    return StoredSupportRun(
        run_id=row["run_id"],
        question=row["question"],
        request_payload=json.loads(row["request_payload"]),
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


def insert_ticket(
    run_id: str,
    summary: str,
    sqlite_path: Optional[str] = None,
) -> TicketRecord:
    target_db = sqlite_path or _default_sqlite_path()
    now = _utc_now().isoformat()
    ticket_id = str(uuid4())
    with _connect(target_db) as connection:
        connection.execute(
            """
            INSERT INTO tickets (
                ticket_id,
                run_id,
                status,
                summary,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, run_id, TicketStatus.OPEN.value, summary, now, now),
        )
        connection.commit()
    return get_ticket(ticket_id, sqlite_path=target_db)  # type: ignore[return-value]


def insert_retrieval_hits(
    run_id: str,
    hits: List[Dict[str, Any]],
    sqlite_path: Optional[str] = None,
) -> None:
    if not hits:
        return
    target_db = sqlite_path or _default_sqlite_path()
    now = _utc_now().isoformat()
    with _connect(target_db) as connection:
        connection.executemany(
            """
            INSERT INTO retrieval_hits (
                run_id,
                source_url,
                title,
                snippet,
                score,
                snapshot_version,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    hit["source_url"],
                    hit.get("title"),
                    hit["snippet"],
                    hit.get("score"),
                    hit["snapshot_version"],
                    now,
                )
                for hit in hits
            ],
        )
        connection.commit()


def upsert_document_snapshot(
    snapshot_id: str,
    requested_url: str,
    final_url: str,
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
            ON CONFLICT(snapshot_id) DO UPDATE SET
                source_url = excluded.source_url,
                requested_url = excluded.requested_url,
                final_url = excluded.final_url,
                fetched_at = excluded.fetched_at,
                content_hash = excluded.content_hash,
                snapshot_version = excluded.snapshot_version,
                title = excluded.title,
                stored_path = excluded.stored_path
            """,
            (
                snapshot_id,
                requested_url,
                requested_url,
                final_url,
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
            SELECT
                snapshot_id,
                source_url,
                COALESCE(requested_url, source_url) AS requested_url,
                COALESCE(final_url, requested_url, source_url) AS final_url,
                fetched_at,
                content_hash,
                snapshot_version,
                title,
                stored_path,
                created_at
            FROM document_snapshots
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        ).fetchone()
    if row is None:
        return None
    return _snapshot_row_to_record(row)


def get_document_snapshot_by_requested_url(
    requested_url: str,
    snapshot_version: str,
    sqlite_path: Optional[str] = None,
) -> Optional[SnapshotRecord]:
    target_db = sqlite_path or _default_sqlite_path()
    with _connect(target_db) as connection:
        row = connection.execute(
            """
            SELECT
                snapshot_id,
                source_url,
                COALESCE(requested_url, source_url) AS requested_url,
                COALESCE(final_url, requested_url, source_url) AS final_url,
                fetched_at,
                content_hash,
                snapshot_version,
                title,
                stored_path,
                created_at
            FROM document_snapshots
            WHERE snapshot_version = ?
              AND COALESCE(requested_url, source_url) = ?
            """,
            (snapshot_version, requested_url),
        ).fetchone()
    if row is None:
        return None
    return _snapshot_row_to_record(row)


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


def list_document_snapshots(snapshot_version: str, sqlite_path: Optional[str] = None) -> List[SnapshotRecord]:
    target_db = sqlite_path or _default_sqlite_path()
    with _connect(target_db) as connection:
        rows = connection.execute(
            """
            SELECT
                snapshot_id,
                source_url,
                COALESCE(requested_url, source_url) AS requested_url,
                COALESCE(final_url, requested_url, source_url) AS final_url,
                fetched_at,
                content_hash,
                snapshot_version,
                title,
                stored_path,
                created_at
            FROM document_snapshots
            WHERE snapshot_version = ?
            ORDER BY COALESCE(requested_url, source_url)
            """,
            (snapshot_version,),
        ).fetchall()
    return [_snapshot_row_to_record(row) for row in rows]


def count_document_chunks(snapshot_version: Optional[str] = None, sqlite_path: Optional[str] = None) -> int:
    target_db = sqlite_path or _default_sqlite_path()
    query = "SELECT COUNT(*) AS total FROM document_chunks"
    parameters: tuple[str, ...] = ()
    if snapshot_version is not None:
        query += " WHERE snapshot_version = ?"
        parameters = (snapshot_version,)
    with _connect(target_db) as connection:
        row = connection.execute(query, parameters).fetchone()
    return int(row["total"]) if row is not None else 0


def count_retrieval_hits(run_id: Optional[str] = None, sqlite_path: Optional[str] = None) -> int:
    target_db = sqlite_path or _default_sqlite_path()
    query = "SELECT COUNT(*) AS total FROM retrieval_hits"
    parameters: tuple[str, ...] = ()
    if run_id is not None:
        query += " WHERE run_id = ?"
        parameters = (run_id,)
    with _connect(target_db) as connection:
        row = connection.execute(query, parameters).fetchone()
    return int(row["total"]) if row is not None else 0


def count_tickets(sqlite_path: Optional[str] = None) -> int:
    target_db = sqlite_path or _default_sqlite_path()
    with _connect(target_db) as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM tickets").fetchone()
    return int(row["total"]) if row is not None else 0


def _default_sqlite_path() -> str:
    from app.core.config import get_settings

    return get_settings().sqlite_path


def _apply_migrations(connection: sqlite3.Connection) -> None:
    _ensure_document_snapshot_schema(connection)


def _ensure_document_snapshot_schema(connection: sqlite3.Connection) -> None:
    columns = _table_columns(connection, "document_snapshots")
    if not columns:
        return

    if "requested_url" not in columns:
        connection.execute("ALTER TABLE document_snapshots ADD COLUMN requested_url TEXT")
    if "final_url" not in columns:
        connection.execute("ALTER TABLE document_snapshots ADD COLUMN final_url TEXT")

    connection.execute(
        """
        UPDATE document_snapshots
        SET requested_url = COALESCE(requested_url, source_url)
        WHERE requested_url IS NULL OR requested_url = ''
        """
    )
    connection.execute(
        """
        UPDATE document_snapshots
        SET final_url = COALESCE(final_url, requested_url, source_url)
        WHERE final_url IS NULL OR final_url = ''
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_document_snapshots_requested_version
            ON document_snapshots (snapshot_version, requested_url)
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_snapshots_final_version
            ON document_snapshots (snapshot_version, final_url)
        """
    )


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def _snapshot_row_to_record(row: sqlite3.Row) -> SnapshotRecord:
    return SnapshotRecord(
        snapshot_id=row["snapshot_id"],
        source_url=row["source_url"],
        requested_url=row["requested_url"],
        final_url=row["final_url"],
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
        content_hash=row["content_hash"],
        snapshot_version=row["snapshot_version"],
        title=row["title"],
        stored_path=row["stored_path"],
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )
