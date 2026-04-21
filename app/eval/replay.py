from __future__ import annotations

import sqlite3
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.core.config import Settings
from app.ingest.fetch import load_source_manifest
from app.models.api import Category, RunStatus, SlotName, SupportAskRequest, SupportAskResponse, SupportSlots
from app.support.service import handle_support_request


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    category: Category
    type: str
    question: Optional[str] = None
    context_slots: Dict[str, str] = field(default_factory=dict)
    expected_status: Optional[RunStatus] = None
    required_source_urls: List[str] = field(default_factory=list)
    expected_missing_slots: List[SlotName] = field(default_factory=list)
    initial_question: Optional[str] = None
    expected_initial_status: Optional[RunStatus] = None
    follow_up_question: Optional[str] = None
    expected_follow_up_status: Optional[RunStatus] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class EvalSuite:
    suite_id: str
    target_snapshot_version: str
    cases: List[EvalCase]


@dataclass(frozen=True)
class EvalPreflight:
    snapshot_version: str
    snapshot_count: int
    chunk_count: int


@dataclass(frozen=True)
class EvalCaseResult:
    case_id: str
    category: str
    type: str
    passed: bool
    expected_status: Optional[str]
    actual_status: Optional[str]
    expected_category: str
    actual_category: str
    citation_hit: Optional[bool]
    clarification_slot_match: Optional[bool]
    ticket_path_pass: Optional[bool]
    expected_follow_up_status: Optional[str]
    actual_follow_up_status: Optional[str]
    failures: List[str]
    notes: Optional[str]


@dataclass(frozen=True)
class EvalSummary:
    suite_id: str
    snapshot_version: str
    min_score: float
    case_count: int
    status_accuracy: float
    category_accuracy: float
    answered_case_count: int
    answered_citation_hit_rate: float
    clarification_case_count: int
    clarification_slot_match_rate: float
    ticket_case_count: int
    ticket_path_pass_rate: float
    false_answered_case_ids: List[str]
    failed_case_ids: List[str]


@dataclass(frozen=True)
class EvalRunResult:
    summary: EvalSummary
    cases: List[EvalCaseResult]


def load_eval_suite(eval_path: Path) -> EvalSuite:
    payload = yaml.safe_load(eval_path.read_text(encoding="utf-8"))
    cases = [_parse_case(item) for item in payload.get("cases", [])]
    return EvalSuite(
        suite_id=payload["suite_id"],
        target_snapshot_version=payload["target_snapshot_version"],
        cases=cases,
    )


def preflight_eval(settings: Settings, suite: EvalSuite) -> EvalPreflight:
    manifest = load_source_manifest(Path(settings.source_manifest_path))
    snapshot_version = manifest.snapshot_version
    if snapshot_version != suite.target_snapshot_version:
        raise RuntimeError(
            f"Eval suite targets snapshot_version='{suite.target_snapshot_version}' "
            f"but current manifest is '{snapshot_version}'."
        )

    snapshot_count, chunk_count = _load_preflight_counts(
        sqlite_path=Path(settings.sqlite_path),
        snapshot_version=snapshot_version,
    )
    if snapshot_count <= 0 or chunk_count <= 0:
        missing_parts: List[str] = []
        if snapshot_count <= 0:
            missing_parts.append("document_snapshots")
        if chunk_count <= 0:
            missing_parts.append("document_chunks")
        raise _preflight_error(
            "Replay eval preflight failed because the current snapshot corpus is incomplete for "
            f"snapshot_version='{snapshot_version}'. Empty or missing data: {', '.join(missing_parts)}."
        )

    return EvalPreflight(
        snapshot_version=snapshot_version,
        snapshot_count=snapshot_count,
        chunk_count=chunk_count,
    )


def run_eval_suite(settings: Settings, suite: EvalSuite, min_score: Optional[float] = None) -> EvalRunResult:
    effective_min_score = min_score if min_score is not None else settings.min_score

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_db = Path(temp_dir) / "eval.db"
        shutil.copy2(settings.sqlite_path, temp_db)
        eval_settings = settings.model_copy(
            update={
                "sqlite_path": str(temp_db),
                "min_score": effective_min_score,
            }
        )

        results = [_evaluate_case(case=case, settings=eval_settings) for case in suite.cases]

    summary = _summarize_results(
        suite=suite,
        snapshot_version=suite.target_snapshot_version,
        min_score=effective_min_score,
        case_results=results,
    )
    return EvalRunResult(summary=summary, cases=results)


def serialize_eval_run(result: EvalRunResult) -> Dict[str, Any]:
    return {
        "summary": asdict(result.summary),
        "cases": [asdict(case) for case in result.cases],
    }


def _parse_case(payload: Dict[str, Any]) -> EvalCase:
    return EvalCase(
        case_id=payload["case_id"],
        category=Category(payload["category"]),
        type=payload["type"],
        question=payload.get("question"),
        context_slots=dict(payload.get("context_slots", {})),
        expected_status=RunStatus(payload["expected_status"]) if payload.get("expected_status") else None,
        required_source_urls=list(payload.get("required_source_urls", [])),
        expected_missing_slots=[SlotName(item) for item in payload.get("expected_missing_slots", [])],
        initial_question=payload.get("initial_question"),
        expected_initial_status=RunStatus(payload["expected_initial_status"]) if payload.get("expected_initial_status") else None,
        follow_up_question=payload.get("follow_up_question"),
        expected_follow_up_status=RunStatus(payload["expected_follow_up_status"]) if payload.get("expected_follow_up_status") else None,
        notes=payload.get("notes"),
    )


def _evaluate_case(case: EvalCase, settings: Settings) -> EvalCaseResult:
    initial_request = SupportAskRequest(
        question=case.initial_question or case.question or "",
        context_slots=SupportSlots(**case.context_slots),
    )
    initial_response = handle_support_request(initial_request, settings)

    expected_status = case.expected_initial_status or case.expected_status
    failures: List[str] = []

    if initial_response.run.status != expected_status:
        failures.append(
            f"initial status expected '{expected_status.value}' but got '{initial_response.run.status.value}'"
        )
    if initial_response.run.category != case.category:
        failures.append(
            f"category expected '{case.category.value}' but got '{initial_response.run.category.value}'"
        )

    citation_hit: Optional[bool] = None
    clarification_slot_match: Optional[bool] = None
    ticket_path_pass: Optional[bool] = None
    follow_up_status: Optional[RunStatus] = None

    if case.type == "single_turn" and case.expected_status is RunStatus.ANSWERED:
        citation_sources = {citation.source_url for citation in initial_response.citations}
        required_sources = set(case.required_source_urls)
        citation_hit = bool(citation_sources.intersection(required_sources))
        if not citation_hit:
            failures.append(
                "answered citations did not hit required_source_urls"
            )

    if expected_status is RunStatus.NEEDS_CLARIFICATION:
        actual_missing_slots = (
            set(initial_response.clarification.missing_slots)
            if initial_response.clarification is not None
            else set()
        )
        clarification_slot_match = actual_missing_slots == set(case.expected_missing_slots)
        if not clarification_slot_match:
            failures.append(
                "clarification missing_slots did not match expected_missing_slots"
            )

    if case.type == "single_turn" and case.expected_status is RunStatus.TICKET_CREATED:
        ticket_path_pass = initial_response.ticket is not None
        if not ticket_path_pass:
            failures.append("expected a ticket record for ticket_created")

    if case.type == "two_turn":
        if initial_response.run.status == RunStatus.NEEDS_CLARIFICATION:
            follow_up_response = handle_support_request(
                SupportAskRequest(
                    question=case.follow_up_question or "",
                    follow_up_run_id=initial_response.run.run_id,
                ),
                settings,
            )
            follow_up_status = follow_up_response.run.status
            ticket_path_pass = (
                follow_up_status == case.expected_follow_up_status
                and follow_up_response.ticket is not None
            )
            if follow_up_status != case.expected_follow_up_status:
                failures.append(
                    f"follow-up status expected '{case.expected_follow_up_status.value}' "
                    f"but got '{follow_up_status.value}'"
                )
            if follow_up_response.ticket is None:
                failures.append("follow-up ticket record was missing")
        else:
            ticket_path_pass = False
            failures.append(
                "follow-up was not executed because the initial response did not request clarification"
            )

    return EvalCaseResult(
        case_id=case.case_id,
        category=case.category.value,
        type=case.type,
        passed=not failures,
        expected_status=expected_status.value if expected_status else None,
        actual_status=initial_response.run.status.value,
        expected_category=case.category.value,
        actual_category=initial_response.run.category.value,
        citation_hit=citation_hit,
        clarification_slot_match=clarification_slot_match,
        ticket_path_pass=ticket_path_pass,
        expected_follow_up_status=case.expected_follow_up_status.value if case.expected_follow_up_status else None,
        actual_follow_up_status=follow_up_status.value if follow_up_status else None,
        failures=failures,
        notes=case.notes,
    )


def _summarize_results(
    suite: EvalSuite,
    snapshot_version: str,
    min_score: float,
    case_results: List[EvalCaseResult],
) -> EvalSummary:
    answered_cases = [case for case in suite.cases if case.expected_status is RunStatus.ANSWERED]
    clarification_cases = [
        case for case in suite.cases if (case.expected_initial_status or case.expected_status) is RunStatus.NEEDS_CLARIFICATION
    ]
    ticket_cases = [
        case
        for case in suite.cases
        if case.expected_status is RunStatus.TICKET_CREATED or case.expected_follow_up_status is RunStatus.TICKET_CREATED
    ]

    status_hits = sum(
        1
        for result in case_results
        if result.actual_status == result.expected_status
    )
    category_hits = sum(
        1
        for result in case_results
        if result.actual_category == result.expected_category
    )
    answered_hits = sum(1 for result in case_results if result.citation_hit is True)
    clarification_hits = sum(1 for result in case_results if result.clarification_slot_match is True)
    ticket_hits = sum(1 for result in case_results if result.ticket_path_pass is True)

    false_answered_case_ids = [
        result.case_id
        for result in case_results
        if result.actual_status == RunStatus.ANSWERED.value and result.expected_status != RunStatus.ANSWERED.value
    ]
    failed_case_ids = [result.case_id for result in case_results if not result.passed]

    return EvalSummary(
        suite_id=suite.suite_id,
        snapshot_version=snapshot_version,
        min_score=min_score,
        case_count=len(case_results),
        status_accuracy=_safe_rate(status_hits, len(case_results)),
        category_accuracy=_safe_rate(category_hits, len(case_results)),
        answered_case_count=len(answered_cases),
        answered_citation_hit_rate=_safe_rate(answered_hits, len(answered_cases)),
        clarification_case_count=len(clarification_cases),
        clarification_slot_match_rate=_safe_rate(clarification_hits, len(clarification_cases)),
        ticket_case_count=len(ticket_cases),
        ticket_path_pass_rate=_safe_rate(ticket_hits, len(ticket_cases)),
        false_answered_case_ids=false_answered_case_ids,
        failed_case_ids=failed_case_ids,
    )


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _load_preflight_counts(sqlite_path: Path, snapshot_version: str) -> tuple[int, int]:
    if not sqlite_path.exists():
        raise _preflight_error(
            f"Replay eval preflight failed because SQLite database '{sqlite_path}' does not exist."
        )

    try:
        with sqlite3.connect(sqlite_path) as connection:
            missing_tables = [
                table_name
                for table_name in ("document_snapshots", "document_chunks")
                if not _table_exists(connection, table_name)
            ]
            if missing_tables:
                raise _preflight_error(
                    "Replay eval preflight failed because required tables are missing from the SQLite database: "
                    f"{', '.join(missing_tables)}."
                )

            snapshot_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM document_snapshots
                    WHERE snapshot_version = ?
                    """,
                    (snapshot_version,),
                ).fetchone()[0]
            )
            chunk_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM document_chunks
                    WHERE snapshot_version = ?
                    """,
                    (snapshot_version,),
                ).fetchone()[0]
            )
            return snapshot_count, chunk_count
    except RuntimeError:
        raise
    except sqlite3.Error as exc:
        raise _preflight_error(
            "Replay eval preflight failed because the SQLite database could not be inspected safely. "
            f"Underlying SQLite error class: {exc.__class__.__name__}."
        ) from None


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _preflight_error(message: str) -> RuntimeError:
    return RuntimeError(
        message
        + " Run '.\\.venv\\Scripts\\python scripts\\fetch_sources.py' and "
        + "'.\\.venv\\Scripts\\python scripts\\build_index.py' first."
    )
