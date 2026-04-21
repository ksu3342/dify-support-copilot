from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Optional


DEFAULT_TARGET_CHARS = 1000
DEFAULT_MIN_CHARS = 400


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    snapshot_id: str
    source_url: str
    snapshot_version: str
    title: Optional[str]
    chunk_index: int
    content: str
    char_count: int


def build_chunk_id(snapshot_version: str, source_url: str, chunk_index: int) -> str:
    digest = hashlib.sha256(f"{snapshot_version}|{source_url}|{chunk_index}".encode("utf-8")).hexdigest()
    return f"chunk_{digest[:24]}"


def split_text_into_chunks(
    text: str,
    target_chars: int = DEFAULT_TARGET_CHARS,
    min_chunk_chars: int = DEFAULT_MIN_CHARS,
) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    chunks: List[str] = []
    current_lines: List[str] = []
    current_length = 0

    for line in lines:
        line_length = len(line)
        proposed_length = current_length + line_length + (1 if current_lines else 0)
        if current_lines and current_length >= min_chunk_chars and proposed_length > target_chars:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_length = line_length
            continue

        current_lines.append(line)
        current_length = proposed_length

    if current_lines:
        trailing_chunk = "\n".join(current_lines)
        if chunks and len(trailing_chunk) < min_chunk_chars:
            chunks[-1] = f"{chunks[-1]}\n{trailing_chunk}"
        else:
            chunks.append(trailing_chunk)

    return chunks


def build_chunks_for_document(
    snapshot_id: str,
    source_url: str,
    snapshot_version: str,
    title: Optional[str],
    text: str,
    target_chars: int = DEFAULT_TARGET_CHARS,
    min_chunk_chars: int = DEFAULT_MIN_CHARS,
) -> List[ChunkRecord]:
    chunks = split_text_into_chunks(
        text=text,
        target_chars=target_chars,
        min_chunk_chars=min_chunk_chars,
    )
    return [
        ChunkRecord(
            chunk_id=build_chunk_id(snapshot_version=snapshot_version, source_url=source_url, chunk_index=index),
            snapshot_id=snapshot_id,
            source_url=source_url,
            snapshot_version=snapshot_version,
            title=title,
            chunk_index=index,
            content=chunk_text,
            char_count=len(chunk_text),
        )
        for index, chunk_text in enumerate(chunks)
    ]
