from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import get_settings
from app.retrieval.index import build_index


def main() -> int:
    summary = build_index(get_settings())
    print(f"snapshot_version: {summary.snapshot_version}")
    print(f"processed_clean_files: {summary.processed_clean_files}")
    print(f"chunk_count: {summary.chunk_count}")
    print(f"retrieval_backend: {summary.backend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
