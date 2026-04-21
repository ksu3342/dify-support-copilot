import sqlite3

import pytest

from app.core.config import REPO_ROOT, get_settings
from app.eval.replay import load_eval_suite, preflight_eval


def test_support_eval_suite_is_tracked_and_covers_required_paths():
    suite = load_eval_suite(REPO_ROOT / "data" / "evals" / "support_eval_v1.yaml")

    categories = [case.category.value for case in suite.cases if case.category.value != "unclassified"]
    single_statuses = [case.expected_status.value for case in suite.cases if case.expected_status is not None]
    two_turn_cases = [case for case in suite.cases if case.type == "two_turn"]

    assert suite.target_snapshot_version == "dify-docs-en-2026-04-21-v2"
    assert len(suite.cases) >= 16
    assert categories.count("deployment") >= 3
    assert categories.count("configuration") >= 3
    assert categories.count("knowledge-base") >= 3
    assert categories.count("integration") >= 3
    assert "answered" in single_statuses
    assert "needs_clarification" in single_statuses
    assert "ticket_created" in single_statuses
    assert len(two_turn_cases) >= 4


def test_preflight_eval_reports_missing_sqlite_with_actionable_message(tmp_path):
    suite = load_eval_suite(REPO_ROOT / "data" / "evals" / "support_eval_v1.yaml")
    settings = get_settings().model_copy(update={"sqlite_path": str(tmp_path / "missing-eval.db")})

    with pytest.raises(RuntimeError) as exc_info:
        preflight_eval(settings=settings, suite=suite)

    message = str(exc_info.value)
    assert "does not exist" in message
    assert ".\\.venv\\Scripts\\python scripts\\fetch_sources.py" in message
    assert ".\\.venv\\Scripts\\python scripts\\build_index.py" in message


def test_preflight_eval_reports_missing_tables_without_leaking_sqlite_details(tmp_path):
    suite = load_eval_suite(REPO_ROOT / "data" / "evals" / "support_eval_v1.yaml")
    sqlite_path = tmp_path / "empty.db"
    with sqlite3.connect(sqlite_path):
        pass
    settings = get_settings().model_copy(update={"sqlite_path": str(sqlite_path)})

    with pytest.raises(RuntimeError) as exc_info:
        preflight_eval(settings=settings, suite=suite)

    message = str(exc_info.value)
    assert "required tables are missing" in message
    assert "document_snapshots" in message
    assert "document_chunks" in message
    assert "no such table" not in message.lower()
    assert ".\\.venv\\Scripts\\python scripts\\fetch_sources.py" in message
    assert ".\\.venv\\Scripts\\python scripts\\build_index.py" in message
