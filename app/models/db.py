import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from app.models.api import Category, RunRecord, RunStatus, TicketRecord, TicketStatus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_parent_dir(sqlite_path: str) -> None:
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)


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


def _default_sqlite_path() -> str:
    from app.core.config import get_settings

    return get_settings().sqlite_path
