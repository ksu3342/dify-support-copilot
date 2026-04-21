from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import get_settings
from app.ingest.fetch import fetch_all_sources


def main() -> int:
    summary = fetch_all_sources(get_settings())

    print(f"snapshot_version: {summary.snapshot_version}")
    print(f"total_pages: {summary.total_pages}")
    print(f"successful_pages: {summary.success_count}")
    print(f"failed_pages: {summary.failure_count}")
    print(f"raw_root: {summary.raw_root}")
    print(f"clean_root: {summary.clean_root}")
    print(f"sqlite_rows_for_snapshot_version: {summary.sqlite_rows_for_snapshot_version}")
    if summary.failures:
        print("failed_urls:")
        for failure in summary.failures:
            print(f"- {failure.source_url} :: {failure.error}")
        return 1

    print("failed_urls: []")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
