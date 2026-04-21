from app.retrieval.chunk import build_chunk_id, build_chunks_for_document, split_text_into_chunks


def test_split_text_into_chunks_is_deterministic():
    text = "\n".join(
        [
            "Docker Compose",
            "Install Dify with Docker Compose on a self-hosted server.",
            "Environment Variables",
            "Set the required environment variables before startup.",
            "Troubleshooting",
            "Check container logs when startup fails.",
        ]
    )

    first = split_text_into_chunks(text=text, target_chars=90, min_chunk_chars=40)
    second = split_text_into_chunks(text=text, target_chars=90, min_chunk_chars=40)

    assert first == second
    assert len(first) >= 2


def test_build_chunks_for_document_generates_stable_chunk_ids():
    text = "\n".join(
        [
            "Configure the Chunk Settings",
            "Adjust delimiters and chunk length for knowledge processing.",
            "Chunk overlap can help preserve context between adjacent chunks.",
            "Use retrieval testing to validate the results.",
        ]
    )

    first = build_chunks_for_document(
        snapshot_id="snap_1",
        source_url="https://docs.dify.ai/en/guides/knowledge-base/create-knowledge-and-upload-documents/chunking-and-cleaning-text",
        snapshot_version="dify-docs-en-2026-04-21-v1",
        title="Configure the Chunk Settings",
        text=text,
        target_chars=80,
        min_chunk_chars=30,
    )
    second = build_chunks_for_document(
        snapshot_id="snap_1",
        source_url="https://docs.dify.ai/en/guides/knowledge-base/create-knowledge-and-upload-documents/chunking-and-cleaning-text",
        snapshot_version="dify-docs-en-2026-04-21-v1",
        title="Configure the Chunk Settings",
        text=text,
        target_chars=80,
        min_chunk_chars=30,
    )

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert first[0].chunk_id == build_chunk_id(
        snapshot_version="dify-docs-en-2026-04-21-v1",
        source_url="https://docs.dify.ai/en/guides/knowledge-base/create-knowledge-and-upload-documents/chunking-and-cleaning-text",
        chunk_index=0,
    )
