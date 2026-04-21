from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import httpx
import yaml

from app.core.config import Settings
from app.ingest.clean import extract_title_and_clean_text
from app.models.db import (
    count_document_snapshots,
    get_document_snapshot_by_requested_url,
    init_db,
    upsert_document_snapshot,
)


@dataclass(frozen=True)
class SourcePage:
    url: str
    category: str
    tags: List[str]


@dataclass(frozen=True)
class SourceManifest:
    product: str
    authoritative_language: str
    snapshot_version: str
    pages: List[SourcePage]


@dataclass(frozen=True)
class SnapshotPaths:
    snapshot_id: str
    raw_relative_path: Path
    clean_relative_path: Path
    raw_absolute_path: Path
    clean_absolute_path: Path


@dataclass(frozen=True)
class PageFetchResult:
    source_url: str
    snapshot_id: Optional[str]
    success: bool
    title: Optional[str]
    raw_path: Optional[Path]
    clean_path: Optional[Path]
    content_hash: Optional[str]
    error: Optional[str]


@dataclass(frozen=True)
class FetchSummary:
    snapshot_version: str
    total_pages: int
    success_count: int
    failure_count: int
    failures: List[PageFetchResult]
    raw_root: Path
    clean_root: Path
    sqlite_rows_for_snapshot_version: int


class SnapshotConflictError(RuntimeError):
    pass


def load_source_manifest(manifest_path: Path) -> SourceManifest:
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    pages = [
        SourcePage(
            url=page["url"],
            category=page["category"],
            tags=list(page.get("tags", [])),
        )
        for page in payload.get("pages", [])
    ]
    return SourceManifest(
        product=payload["product"],
        authoritative_language=payload["authoritative_language"],
        snapshot_version=payload["snapshot_version"],
        pages=pages,
    )


def build_snapshot_paths(
    raw_snapshot_root: Path,
    clean_snapshot_root: Path,
    snapshot_version: str,
    source_url: str,
) -> SnapshotPaths:
    parsed = urlparse(source_url)
    raw_root = raw_snapshot_root / snapshot_version
    clean_root = clean_snapshot_root / snapshot_version

    sanitized_parts = [_sanitize_path_part(part) for part in parsed.path.split("/") if part]
    if not sanitized_parts:
        sanitized_parts = ["index"]

    directory_parts = sanitized_parts[:-1]
    filename_stem = sanitized_parts[-1] or "index"
    suffix_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:10]

    raw_relative = Path("data") / "raw" / snapshot_version / Path(*directory_parts) / f"{filename_stem}--{suffix_hash}.html"
    clean_relative = Path("data") / "clean" / snapshot_version / Path(*directory_parts) / f"{filename_stem}--{suffix_hash}.txt"
    snapshot_id = build_snapshot_id(source_url=source_url, snapshot_version=snapshot_version)

    return SnapshotPaths(
        snapshot_id=snapshot_id,
        raw_relative_path=raw_relative,
        clean_relative_path=clean_relative,
        raw_absolute_path=raw_root / Path(*directory_parts) / f"{filename_stem}--{suffix_hash}.html",
        clean_absolute_path=clean_root / Path(*directory_parts) / f"{filename_stem}--{suffix_hash}.txt",
    )


def build_snapshot_id(source_url: str, snapshot_version: str) -> str:
    digest = hashlib.sha256(f"{snapshot_version}|{source_url}".encode("utf-8")).hexdigest()
    return f"snap_{digest[:24]}"


def fetch_all_sources(settings: Settings) -> FetchSummary:
    manifest = load_source_manifest(Path(settings.source_manifest_path))
    init_db(settings.sqlite_path, settings.sqlite_init_script)

    raw_root = Path(settings.raw_snapshot_root) / manifest.snapshot_version
    clean_root = Path(settings.clean_snapshot_root) / manifest.snapshot_version
    raw_root.mkdir(parents=True, exist_ok=True)
    clean_root.mkdir(parents=True, exist_ok=True)

    results: List[PageFetchResult] = []

    with httpx.Client(
        follow_redirects=True,
        timeout=settings.fetch_timeout_seconds,
        headers={"User-Agent": settings.fetch_user_agent},
    ) as client:
        for page in manifest.pages:
            try:
                results.append(
                    _fetch_single_page(
                        client=client,
                        settings=settings,
                        snapshot_version=manifest.snapshot_version,
                        source_url=page.url,
                    )
                )
            except SnapshotConflictError as exc:
                results.append(
                    PageFetchResult(
                        source_url=page.url,
                        snapshot_id=None,
                        success=False,
                        title=None,
                        raw_path=None,
                        clean_path=None,
                        content_hash=None,
                        error=str(exc),
                    )
                )
                break

    failures = [result for result in results if not result.success]
    success_count = sum(1 for result in results if result.success)

    return FetchSummary(
        snapshot_version=manifest.snapshot_version,
        total_pages=len(manifest.pages),
        success_count=success_count,
        failure_count=len(failures),
        failures=failures,
        raw_root=raw_root,
        clean_root=clean_root,
        sqlite_rows_for_snapshot_version=count_document_snapshots(manifest.snapshot_version, sqlite_path=settings.sqlite_path),
    )


def _fetch_single_page(
    client: httpx.Client,
    settings: Settings,
    snapshot_version: str,
    source_url: str,
) -> PageFetchResult:
    try:
        _validate_source_url(source_url)
        response = client.get(source_url)
        response.raise_for_status()
        final_url = str(response.url)
        _validate_source_url(final_url)

        html = response.text
        title, cleaned_text = extract_title_and_clean_text(html)
        fetched_at = datetime.now(timezone.utc)
        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        _assert_snapshot_is_reproducible(
            requested_url=source_url,
            snapshot_version=snapshot_version,
            content_hash=content_hash,
            sqlite_path=settings.sqlite_path,
        )
        paths = build_snapshot_paths(
            raw_snapshot_root=Path(settings.raw_snapshot_root),
            clean_snapshot_root=Path(settings.clean_snapshot_root),
            snapshot_version=snapshot_version,
            source_url=source_url,
        )

        paths.raw_absolute_path.parent.mkdir(parents=True, exist_ok=True)
        paths.clean_absolute_path.parent.mkdir(parents=True, exist_ok=True)
        paths.raw_absolute_path.write_text(html, encoding="utf-8")
        paths.clean_absolute_path.write_text(cleaned_text, encoding="utf-8")

        upsert_document_snapshot(
            snapshot_id=paths.snapshot_id,
            requested_url=source_url,
            final_url=final_url,
            fetched_at=fetched_at,
            content_hash=content_hash,
            snapshot_version=snapshot_version,
            title=title,
            stored_path=paths.raw_relative_path.as_posix(),
            sqlite_path=settings.sqlite_path,
        )
        return PageFetchResult(
            source_url=source_url,
            snapshot_id=paths.snapshot_id,
            success=True,
            title=title,
            raw_path=paths.raw_relative_path,
            clean_path=paths.clean_relative_path,
            content_hash=content_hash,
            error=None,
        )
    except SnapshotConflictError:
        raise
    except Exception as exc:
        return PageFetchResult(
            source_url=source_url,
            snapshot_id=None,
            success=False,
            title=None,
            raw_path=None,
            clean_path=None,
            content_hash=None,
            error=str(exc),
        )


def _sanitize_path_part(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip().lower()).strip("-")
    return sanitized or "index"


def _validate_source_url(source_url: str) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme for source: {source_url}")
    if parsed.netloc != "docs.dify.ai":
        raise ValueError(f"Non-authoritative host is not allowed: {source_url}")


def _assert_snapshot_is_reproducible(
    requested_url: str,
    snapshot_version: str,
    content_hash: str,
    sqlite_path: str,
) -> None:
    existing_snapshot = get_document_snapshot_by_requested_url(
        requested_url=requested_url,
        snapshot_version=snapshot_version,
        sqlite_path=sqlite_path,
    )
    if existing_snapshot is None or existing_snapshot.content_hash == content_hash:
        return

    raise SnapshotConflictError(
        "Snapshot content drift detected for "
        f"snapshot_version='{snapshot_version}' and requested_url='{requested_url}'. "
        f"existing_hash='{existing_snapshot.content_hash}' new_hash='{content_hash}'. "
        "Refusing to overwrite the existing snapshot."
    )
