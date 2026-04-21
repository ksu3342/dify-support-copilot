from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "dify-support-copilot"
    app_env: str = "dev"
    api_prefix: str = "/v1"
    sqlite_path: str = str(REPO_ROOT / "storage" / "copilot.db")
    sqlite_init_script: str = str(REPO_ROOT / "scripts" / "init_db.sql")
    source_manifest_path: str = str(REPO_ROOT / "data" / "sources.yaml")
    raw_snapshot_root: str = str(REPO_ROOT / "data" / "raw")
    clean_snapshot_root: str = str(REPO_ROOT / "data" / "clean")
    fetch_timeout_seconds: float = 20.0
    fetch_user_agent: str = "dify-support-copilot/0.2"
    min_evidence_hits: int = 2
    min_score: float = 0.35
    min_score_note: str = "pending calibration"
    vector_store_backend: str = "lightweight-local-vector-store"

    model_config = SettingsConfigDict(env_prefix="COPILOT_", case_sensitive=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
