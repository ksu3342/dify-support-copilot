from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import List, Optional

from app.core.config import REPO_ROOT, Settings
from app.ingest.fetch import load_source_manifest
from app.models.db import _connect, count_document_chunks, init_db, list_document_snapshots
from app.retrieval.chunk import ChunkRecord, build_chunks_for_document


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    source_url: str
    snapshot_version: str
    title: Optional[str]
    chunk_index: int
    score: float
    snippet: str


@dataclass(frozen=True)
class IndexBuildSummary:
    snapshot_version: str
    processed_clean_files: int
    chunk_count: int
    backend: str


def build_index(settings: Settings) -> IndexBuildSummary:
    manifest = load_source_manifest(Path(settings.source_manifest_path))
    init_db(settings.sqlite_path, settings.sqlite_init_script)

    processed_clean_files, chunks = _load_chunks_from_cleaned_documents(
        settings=settings,
        snapshot_version=manifest.snapshot_version,
    )
    backend = _replace_chunks(
        sqlite_path=settings.sqlite_path,
        snapshot_version=manifest.snapshot_version,
        chunks=chunks,
    )
    return IndexBuildSummary(
        snapshot_version=manifest.snapshot_version,
        processed_clean_files=processed_clean_files,
        chunk_count=count_document_chunks(manifest.snapshot_version, sqlite_path=settings.sqlite_path),
        backend=backend,
    )


def search_index(
    query: str,
    top_k: int,
    sqlite_path: str,
    snapshot_version: Optional[str] = None,
) -> tuple[str, List[SearchResult]]:
    with _connect(sqlite_path) as connection:
        if _fts_table_exists(connection):
            results = _search_with_fts(
                connection=connection,
                query=query,
                top_k=top_k,
                snapshot_version=snapshot_version,
            )
            return "sqlite-fts5", results

        results = _search_with_lexical_fallback(
            connection=connection,
            query=query,
            top_k=top_k,
            snapshot_version=snapshot_version,
        )
        return "lexical-fallback", results


def _load_chunks_from_cleaned_documents(settings: Settings, snapshot_version: str) -> tuple[int, List[ChunkRecord]]:
    snapshots = list_document_snapshots(snapshot_version=snapshot_version, sqlite_path=settings.sqlite_path)
    chunks: List[ChunkRecord] = []
    processed_clean_files = 0
    for snapshot in snapshots:
        if not snapshot.stored_path:
            continue
        clean_path = _derive_clean_path(
            clean_root=Path(settings.clean_snapshot_root),
            stored_path=snapshot.stored_path,
        )
        text = clean_path.read_text(encoding="utf-8")
        processed_clean_files += 1
        chunks.extend(
            build_chunks_for_document(
                snapshot_id=snapshot.snapshot_id,
                source_url=snapshot.source_url,
                snapshot_version=snapshot.snapshot_version,
                title=snapshot.title,
                text=text,
                target_chars=settings.chunk_target_chars,
                min_chunk_chars=settings.chunk_min_chars,
            )
        )
    return processed_clean_files, chunks


def _derive_clean_path(clean_root: Path, stored_path: str) -> Path:
    raw_relative = PurePosixPath(stored_path)
    suffix_parts = list(raw_relative.parts[2:])
    suffix_parts[-1] = str(PurePosixPath(suffix_parts[-1]).with_suffix(".txt"))
    return clean_root.joinpath(*suffix_parts)


def _replace_chunks(sqlite_path: str, snapshot_version: str, chunks: List[ChunkRecord]) -> str:
    with _connect(sqlite_path) as connection:
        backend = "sqlite-fts5" if _ensure_fts_table(connection) else "lexical-fallback"

        existing_chunk_ids = [
            row["chunk_id"]
            for row in connection.execute(
                "SELECT chunk_id FROM document_chunks WHERE snapshot_version = ?",
                (snapshot_version,),
            ).fetchall()
        ]
        if backend == "sqlite-fts5" and existing_chunk_ids:
            placeholders = ",".join("?" for _ in existing_chunk_ids)
            connection.execute(
                f"DELETE FROM document_chunks_fts WHERE chunk_id IN ({placeholders})",
                tuple(existing_chunk_ids),
            )

        connection.execute(
            "DELETE FROM document_chunks WHERE snapshot_version = ?",
            (snapshot_version,),
        )

        now = datetime.now(timezone.utc).isoformat()
        connection.executemany(
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
            [
                (
                    chunk.chunk_id,
                    chunk.snapshot_id,
                    chunk.source_url,
                    chunk.snapshot_version,
                    chunk.title,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.char_count,
                    now,
                    now,
                )
                for chunk in chunks
            ],
        )

        if backend == "sqlite-fts5":
            connection.executemany(
                """
                INSERT INTO document_chunks_fts (chunk_id, title, content)
                VALUES (?, ?, ?)
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.title or "",
                        chunk.content,
                    )
                    for chunk in chunks
                ],
            )

        connection.commit()
    return backend


def _ensure_fts_table(connection: sqlite3.Connection) -> bool:
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
        return True
    except sqlite3.OperationalError:
        return False


def _fts_table_exists(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'document_chunks_fts'
        """
    ).fetchone()
    return row is not None


def _search_with_fts(
    connection: sqlite3.Connection,
    query: str,
    top_k: int,
    snapshot_version: Optional[str],
) -> List[SearchResult]:
    parameters: list[object] = [_fts_query(query)]
    snapshot_filter = ""
    if snapshot_version is not None:
        snapshot_filter = "AND c.snapshot_version = ?"
        parameters.append(snapshot_version)
    parameters.append(top_k)

    rows = connection.execute(
        f"""
        SELECT
            c.chunk_id,
            c.source_url,
            c.snapshot_version,
            c.title,
            c.chunk_index,
            ROUND(-bm25(document_chunks_fts), 6) AS score,
            snippet(document_chunks_fts, 2, '[', ']', ' ... ', 18) AS snippet
        FROM document_chunks_fts
        JOIN document_chunks AS c
            ON c.chunk_id = document_chunks_fts.chunk_id
        WHERE document_chunks_fts MATCH ?
          {snapshot_filter}
        ORDER BY bm25(document_chunks_fts) ASC, c.source_url ASC, c.chunk_index ASC
        LIMIT ?
        """,
        tuple(parameters),
    ).fetchall()
    return [
        SearchResult(
            chunk_id=row["chunk_id"],
            source_url=row["source_url"],
            snapshot_version=row["snapshot_version"],
            title=row["title"],
            chunk_index=int(row["chunk_index"]),
            score=float(row["score"]),
            snippet=row["snippet"],
        )
        for row in rows
    ]


def _search_with_lexical_fallback(
    connection: sqlite3.Connection,
    query: str,
    top_k: int,
    snapshot_version: Optional[str],
) -> List[SearchResult]:
    terms = _query_terms(query)
    sql = """
        SELECT chunk_id, source_url, snapshot_version, title, chunk_index, content
        FROM document_chunks
    """
    parameters: tuple[object, ...] = ()
    if snapshot_version is not None:
        sql += " WHERE snapshot_version = ?"
        parameters = (snapshot_version,)
    rows = connection.execute(sql, parameters).fetchall()

    scored_results: List[SearchResult] = []
    for row in rows:
        haystack = f"{row['title'] or ''}\n{row['content']}".lower()
        score = 0.0
        for term in terms:
            score += haystack.count(term)
            score += 2 * (row["title"] or "").lower().count(term)
        if score <= 0:
            continue
        snippet = _lexical_snippet(row["content"], terms)
        scored_results.append(
            SearchResult(
                chunk_id=row["chunk_id"],
                source_url=row["source_url"],
                snapshot_version=row["snapshot_version"],
                title=row["title"],
                chunk_index=int(row["chunk_index"]),
                score=score,
                snippet=snippet,
            )
        )

    scored_results.sort(key=lambda item: (-item.score, item.source_url, item.chunk_index))
    return scored_results[:top_k]


def _fts_query(query: str) -> str:
    terms = _query_terms(query)
    if not terms:
        return '""'
    return " OR ".join(f'"{term}"' for term in terms)


def _query_terms(query: str) -> List[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in query)
    return [term for term in normalized.split() if term]


def _lexical_snippet(content: str, terms: List[str], window: int = 220) -> str:
    lowered = content.lower()
    for term in terms:
        index = lowered.find(term)
        if index >= 0:
            start = max(0, index - 60)
            end = min(len(content), index + window)
            return content[start:end].replace("\n", " ")
    return content[:window].replace("\n", " ")
