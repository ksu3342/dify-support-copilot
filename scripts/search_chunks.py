import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import get_settings
from app.retrieval.index import search_index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    settings = get_settings()
    backend, results = search_index(
        query=args.query,
        top_k=args.top_k,
        sqlite_path=settings.sqlite_path,
    )

    print(f"backend: {backend}")
    print(f"query: {args.query}")
    print(f"top_k: {args.top_k}")
    print(f"result_count: {len(results)}")
    for rank, result in enumerate(results, start=1):
        print(f"rank: {rank}")
        print(f"score: {result.score}")
        print(f"chunk_id: {result.chunk_id}")
        print(f"source_url: {result.source_url}")
        print(f"snapshot_version: {result.snapshot_version}")
        print(f"title: {result.title or ''}")
        print(f"chunk_index: {result.chunk_index}")
        print(f"snippet: {result.snippet}")
        print("---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
