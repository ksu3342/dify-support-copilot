from pathlib import Path

from app.core.config import REPO_ROOT
from app.ingest.fetch import build_snapshot_id, build_snapshot_paths, load_source_manifest


def test_load_source_manifest_reads_existing_project_file():
    manifest = load_source_manifest(REPO_ROOT / "data" / "sources.yaml")

    assert manifest.product == "Dify"
    assert manifest.authoritative_language == "en"
    assert manifest.snapshot_version == "dify-docs-en-2026-04-21-v2"
    assert len(manifest.pages) >= 24
    assert all(page.url.startswith("https://docs.dify.ai/") for page in manifest.pages)
    assert {
        "https://docs.dify.ai/en/self-host/troubleshooting/common-issues",
        "https://docs.dify.ai/en/self-host/troubleshooting/docker-issues",
        "https://docs.dify.ai/en/self-host/troubleshooting/storage-and-migration",
        "https://docs.dify.ai/en/self-host/troubleshooting/weaviate-v4-migration",
        "https://docs.dify.ai/en/develop-plugin/dev-guides-and-walkthroughs/tool-oauth",
        "https://docs.dify.ai/en/use-dify/nodes/trigger/webhook-trigger",
    }.issubset({page.url for page in manifest.pages})


def test_snapshot_identity_and_paths_are_stable(tmp_path):
    source_url = "https://docs.dify.ai/en/guides/workflow/node/http-request"
    snapshot_version = "dify-docs-en-2026-04-21-v2"

    first_id = build_snapshot_id(source_url=source_url, snapshot_version=snapshot_version)
    second_id = build_snapshot_id(source_url=source_url, snapshot_version=snapshot_version)
    raw_root = tmp_path / "custom-raw"
    clean_root = tmp_path / "custom-clean"
    first_paths = build_snapshot_paths(
        raw_snapshot_root=raw_root,
        clean_snapshot_root=clean_root,
        snapshot_version=snapshot_version,
        source_url=source_url,
    )
    second_paths = build_snapshot_paths(
        raw_snapshot_root=raw_root,
        clean_snapshot_root=clean_root,
        snapshot_version=snapshot_version,
        source_url=source_url,
    )

    assert first_id == second_id
    assert first_paths.snapshot_id == second_paths.snapshot_id
    assert first_paths.raw_relative_path == second_paths.raw_relative_path
    assert first_paths.clean_relative_path == second_paths.clean_relative_path
    assert first_paths.raw_relative_path.as_posix().startswith(f"data/raw/{snapshot_version}/")
    assert first_paths.clean_relative_path.as_posix().startswith(f"data/clean/{snapshot_version}/")
    assert first_paths.raw_absolute_path.as_posix().startswith((raw_root / snapshot_version).as_posix())
    assert first_paths.clean_absolute_path.as_posix().startswith((clean_root / snapshot_version).as_posix())
    assert first_paths.raw_relative_path.suffix == ".html"
    assert first_paths.clean_relative_path.suffix == ".txt"
