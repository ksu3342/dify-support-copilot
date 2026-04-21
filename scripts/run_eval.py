import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import REPO_ROOT as APP_REPO_ROOT, get_settings
from app.eval.replay import load_eval_suite, preflight_eval, run_eval_suite, serialize_eval_run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval-path",
        default=str(APP_REPO_ROOT / "data" / "evals" / "support_eval_v1.yaml"),
    )
    parser.add_argument("--min-score", type=float, default=None)
    args = parser.parse_args()

    settings = get_settings()
    suite = load_eval_suite(Path(args.eval_path))
    preflight = preflight_eval(settings=settings, suite=suite)
    result = run_eval_suite(settings=settings, suite=suite, min_score=args.min_score)

    print(f"suite_id: {result.summary.suite_id}")
    print(f"snapshot_version: {preflight.snapshot_version}")
    print(f"sqlite_path: {settings.sqlite_path}")
    print(f"min_score: {result.summary.min_score}")
    print(f"snapshot_count: {preflight.snapshot_count}")
    print(f"chunk_count: {preflight.chunk_count}")

    for case in result.cases:
        print("---")
        print(f"case_id: {case.case_id}")
        print(f"expected_status: {case.expected_status}")
        print(f"actual_status: {case.actual_status}")
        print(f"expected_category: {case.expected_category}")
        print(f"actual_category: {case.actual_category}")
        print(f"citation_hit: {case.citation_hit}")
        print(f"clarification_slot_match: {case.clarification_slot_match}")
        print(f"ticket_path_pass: {case.ticket_path_pass}")
        if case.expected_follow_up_status is not None:
            print(f"expected_follow_up_status: {case.expected_follow_up_status}")
            print(f"actual_follow_up_status: {case.actual_follow_up_status}")
        print(f"passed: {case.passed}")
        if case.failures:
            print("failures:")
            for failure in case.failures:
                print(f"- {failure}")

    print("---")
    print("summary:")
    print(json.dumps(result.summary.__dict__, indent=2, ensure_ascii=False))

    artifact_dir = REPO_ROOT / "storage" / "evals"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    artifact_path = artifact_dir / f"{result.summary.snapshot_version}-{timestamp}.json"
    artifact_path.write_text(
        json.dumps(serialize_eval_run(result), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"artifact_path: {artifact_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
