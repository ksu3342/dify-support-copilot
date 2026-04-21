from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Dict, List, Optional

from fastapi import HTTPException, status

from app.core.config import Settings
from app.core.readiness import require_support_readiness
from app.ingest.fetch import SourceManifest, SourcePage, load_source_manifest
from app.models.api import (
    Category,
    Citation,
    ClarificationPrompt,
    RunStatus,
    SlotName,
    SupportAskRequest,
    SupportAskResponse,
    SupportSlots,
    TicketRecord,
)
from app.models.db import (
    get_support_run_state,
    insert_retrieval_hits,
    insert_support_run,
    insert_ticket,
)
from app.retrieval.index import SearchResult, search_index


GENERIC_FOLLOW_UP_SLOTS = {
    Category.DEPLOYMENT: [SlotName.VERSION, SlotName.ENVIRONMENT],
    Category.CONFIGURATION: [SlotName.VERSION, SlotName.ENVIRONMENT],
    Category.KNOWLEDGE_BASE: [SlotName.ERROR_MESSAGE, SlotName.ENVIRONMENT],
    Category.INTEGRATION: [SlotName.ERROR_MESSAGE, SlotName.ENVIRONMENT],
}

GUIDANCE_QUERY_PHRASES = (
    "how do i",
    "how can i",
    "what is",
    "explain",
    "show me",
    "guide",
    "setup",
    "set up",
    "configure",
    "develop",
    "add oauth support",
    "test retrieval",
)

PROBLEM_REPORT_PHRASES = (
    "not working",
    "broken",
    "bad",
    "fails",
    "failing",
    "issue",
    "issues",
    "error",
    "not searchable",
    "search is bad",
    "integration is broken",
    "api is broken",
    "wrong",
)


@dataclass(frozen=True)
class ClassificationResult:
    category: Category
    confidence: float


@dataclass(frozen=True)
class SupportDecision:
    status: RunStatus
    answer: Optional[str]
    citations: List[Citation]
    clarification: Optional[ClarificationPrompt]
    ticket_summary: Optional[str]
    retrieval_results: List[SearchResult]
    retrieval_backend: Optional[str]
    resolved_question: str
    resolved_slots: SupportSlots
    category: Category
    confidence: float
    is_follow_up: bool


def handle_support_request(request: SupportAskRequest, settings: Settings) -> SupportAskResponse:
    require_support_readiness(settings)
    manifest = _load_manifest(settings.source_manifest_path)
    previous_run = _load_follow_up_run(request, settings)

    resolved_question = _merge_question(previous_run.question if previous_run else None, request.question)
    resolved_slots = _resolve_slots(request=request, previous_run=previous_run)
    classification = _classify_question(resolved_question)

    retrieval_backend: Optional[str] = None
    retrieval_results: List[SearchResult] = []
    if classification.category is not Category.UNCLASSIFIED:
        retrieval_backend, retrieval_results = _retrieve_evidence(
            question=resolved_question,
            category=classification.category,
            manifest=manifest,
            settings=settings,
        )

    decision = _decide_support_outcome(
        category=classification.category,
        confidence=classification.confidence,
        resolved_question=resolved_question,
        resolved_slots=resolved_slots,
        retrieval_results=retrieval_results,
        retrieval_backend=retrieval_backend,
        settings=settings,
        is_follow_up=previous_run is not None,
    )

    run_payload = {
        "input": request.model_dump(mode="json"),
        "resolved_question": decision.resolved_question,
        "resolved_context_slots": decision.resolved_slots.model_dump(mode="json"),
        "follow_up_run_id": request.follow_up_run_id,
        "is_follow_up": decision.is_follow_up,
        "retrieval_backend": decision.retrieval_backend,
    }
    run = insert_support_run(
        question=decision.resolved_question,
        request_payload=run_payload,
        category=decision.category,
        confidence=decision.confidence,
        status=decision.status,
        sqlite_path=settings.sqlite_path,
    )

    if decision.retrieval_results:
        insert_retrieval_hits(
            run_id=run.run_id,
            hits=[
                {
                    "source_url": result.source_url,
                    "title": result.title,
                    "snippet": _sanitize_snippet(result.snippet),
                    "score": result.score,
                    "snapshot_version": result.snapshot_version,
                }
                for result in decision.retrieval_results
            ],
            sqlite_path=settings.sqlite_path,
        )

    ticket: Optional[TicketRecord] = None
    if decision.ticket_summary is not None:
        ticket = insert_ticket(
            run_id=run.run_id,
            summary=decision.ticket_summary,
            sqlite_path=settings.sqlite_path,
        )

    return SupportAskResponse(
        run=run,
        answer=decision.answer,
        citations=decision.citations,
        clarification=decision.clarification,
        ticket=ticket,
        implemented_capabilities=[
            "deterministic_classification",
            "fixed_slot_extraction",
            "manifest_guided_retrieval",
            "retrieval_hit_logging",
            "ticket_creation",
        ],
        notes=[
            "Day 4 uses a deterministic baseline for classification and answer generation. No remote LLM is called.",
            "Retrieval is filtered by manifest category and lightly boosted by manifest tags.",
        ],
    )


def _load_follow_up_run(request: SupportAskRequest, settings: Settings):
    if request.follow_up_run_id is None:
        return None
    previous_run = get_support_run_state(request.follow_up_run_id, sqlite_path=settings.sqlite_path)
    if previous_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{request.follow_up_run_id}' was not found.",
        )
    if previous_run.status is not RunStatus.NEEDS_CLARIFICATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="follow_up_run_id can only reference a run that requested clarification.",
        )
    return previous_run


def _merge_question(previous_question: Optional[str], current_question: str) -> str:
    if not previous_question:
        return current_question.strip()
    return f"{previous_question.strip()}\n{current_question.strip()}".strip()


def _resolve_slots(request: SupportAskRequest, previous_run) -> SupportSlots:
    merged = SupportSlots()
    if previous_run is not None:
        previous_payload = previous_run.request_payload
        resolved_context = previous_payload.get("resolved_context_slots")
        if isinstance(resolved_context, dict):
            merged = SupportSlots(**resolved_context)
        else:
            raw_context = previous_payload.get("input", {}).get("context_slots", {})
            if isinstance(raw_context, dict):
                merged = SupportSlots(**raw_context)

    merged = _merge_slot_models(merged, request.context_slots)
    extracted = _extract_slots(_merge_question(previous_run.question if previous_run else None, request.question))
    return _merge_slot_models(merged, extracted)


def _merge_slot_models(base: SupportSlots, override: SupportSlots) -> SupportSlots:
    merged = base.model_dump(mode="json")
    for field, value in override.model_dump(mode="json").items():
        if value:
            merged[field] = value
    return SupportSlots(**merged)


def _extract_slots(question: str) -> SupportSlots:
    lower_question = question.lower()

    deployment_method = None
    for candidate in ("docker compose", "docker-compose", "docker", "kubernetes", "k8s", "helm"):
        if candidate in lower_question:
            deployment_method = candidate
            break

    version_match = re.search(r"\bv?\d+\.\d+(?:\.\d+)?\b", question, re.IGNORECASE)
    environment = None
    for candidate in (
        "windows 11",
        "windows",
        "ubuntu",
        "linux",
        "macos",
        "mac",
        "docker desktop",
        "kubernetes",
        "k8s",
        "production",
        "staging",
        "development",
        "local",
    ):
        if candidate in lower_question:
            environment = candidate
            break

    error_message = None
    if any(token in lower_question for token in ("error", "failed", "fails", "failing", "failure", "exception", "traceback")):
        error_message = question.strip()[:280]

    return SupportSlots(
        deployment_method=deployment_method,
        version=version_match.group(0) if version_match else None,
        error_message=error_message,
        environment=environment,
    )


def _classify_question(question: str) -> ClassificationResult:
    normalized = question.lower()
    category_scores = {
        Category.DEPLOYMENT: _weighted_score(
            normalized,
            {
                "docker compose": 4,
                "docker-compose": 4,
                "self-hosted": 4,
                "deploy": 3,
                "install": 3,
                "upgrade": 2,
                "container": 2,
                "environment variable": 2,
                "env": 1,
                "kubernetes": 3,
                "helm": 3,
                "startup": 1,
            },
        ),
        Category.CONFIGURATION: _weighted_score(
            normalized,
            {
                "configure": 3,
                "configuration": 3,
                "settings": 2,
                "schema": 3,
                "model provider": 3,
                "provider": 2,
                "if else": 2,
                "question classifier": 2,
                "workflow node": 1,
            },
        ),
        Category.KNOWLEDGE_BASE: _weighted_score(
            normalized,
            {
                "knowledge base": 5,
                "knowledge": 3,
                "chunk": 4,
                "retrieval": 3,
                "indexing": 3,
                "document": 2,
                "citation": 2,
                "upload": 2,
            },
        ),
        Category.INTEGRATION: _weighted_score(
            normalized,
            {
                "api": 4,
                "plugin": 3,
                "plugins": 3,
                "tool": 2,
                "tools": 2,
                "http request": 3,
                "integrate": 3,
                "integration": 3,
                "backend": 2,
                "publish": 2,
                "workflow": 1,
            },
        ),
    }

    ranked = sorted(category_scores.items(), key=lambda item: item[1], reverse=True)
    best_category, best_score = ranked[0]
    second_score = ranked[1][1]
    if best_score <= 0 or best_score == second_score:
        return ClassificationResult(category=Category.UNCLASSIFIED, confidence=0.0)

    confidence = min(0.95, 0.45 + 0.08 * best_score)
    return ClassificationResult(category=best_category, confidence=round(confidence, 2))


def _weighted_score(normalized_question: str, weights: Dict[str, int]) -> int:
    return sum(weight for phrase, weight in weights.items() if phrase in normalized_question)


def _decide_support_outcome(
    category: Category,
    confidence: float,
    resolved_question: str,
    resolved_slots: SupportSlots,
    retrieval_results: List[SearchResult],
    retrieval_backend: Optional[str],
    settings: Settings,
    is_follow_up: bool,
) -> SupportDecision:
    if category is Category.UNCLASSIFIED:
        return SupportDecision(
            status=RunStatus.TICKET_CREATED,
            answer=None,
            citations=[],
            clarification=None,
            ticket_summary="Escalated because the request could not be stably classified into deployment, configuration, knowledge-base, or integration.",
            retrieval_results=[],
            retrieval_backend=None,
            resolved_question=resolved_question,
            resolved_slots=resolved_slots,
            category=category,
            confidence=confidence,
            is_follow_up=is_follow_up,
        )

    missing_slots = _missing_slots(resolved_slots)
    needs_slot_clarification = (
        category in {Category.DEPLOYMENT, Category.CONFIGURATION} and len(missing_slots) >= 2
    ) or _needs_non_deployment_clarification(
        category=category,
        resolved_question=resolved_question,
        resolved_slots=resolved_slots,
    )
    evidence_count = len(retrieval_results)
    top_score = retrieval_results[0].score if retrieval_results else 0.0
    insufficient_evidence = evidence_count < settings.min_evidence_hits or top_score < settings.min_score

    if is_follow_up and (needs_slot_clarification or insufficient_evidence):
        missing_for_ticket = missing_slots or GENERIC_FOLLOW_UP_SLOTS.get(category, [SlotName.ERROR_MESSAGE, SlotName.ENVIRONMENT])
        return SupportDecision(
            status=RunStatus.TICKET_CREATED,
            answer=None,
            citations=[],
            clarification=None,
            ticket_summary=_build_ticket_summary(
                category=category,
                evidence_count=evidence_count,
                top_score=top_score,
                missing_slots=missing_for_ticket,
                is_follow_up=True,
            ),
            retrieval_results=retrieval_results,
            retrieval_backend=retrieval_backend,
            resolved_question=resolved_question,
            resolved_slots=resolved_slots,
            category=category,
            confidence=confidence,
            is_follow_up=is_follow_up,
        )

    if needs_slot_clarification or insufficient_evidence:
        clarification_slots = missing_slots or GENERIC_FOLLOW_UP_SLOTS.get(category, [SlotName.ERROR_MESSAGE, SlotName.ENVIRONMENT])
        return SupportDecision(
            status=RunStatus.NEEDS_CLARIFICATION,
            answer=None,
            citations=[],
            clarification=ClarificationPrompt(
                question=_build_clarification_question(category=category, missing_slots=clarification_slots),
                missing_slots=clarification_slots,
            ),
            ticket_summary=None,
            retrieval_results=retrieval_results,
            retrieval_backend=retrieval_backend,
            resolved_question=resolved_question,
            resolved_slots=resolved_slots,
            category=category,
            confidence=confidence,
            is_follow_up=is_follow_up,
        )

    citations = [
        Citation(
            chunk_id=result.chunk_id,
            source_url=result.source_url,
            snapshot_version=result.snapshot_version,
            title=result.title,
            chunk_index=result.chunk_index,
            snippet=_sanitize_snippet(result.snippet),
        )
        for result in retrieval_results[: settings.support_citation_top_k]
    ]
    answer = _build_answer(retrieval_results[: settings.support_citation_top_k])
    return SupportDecision(
        status=RunStatus.ANSWERED,
        answer=answer,
        citations=citations,
        clarification=None,
        ticket_summary=None,
        retrieval_results=retrieval_results,
        retrieval_backend=retrieval_backend,
        resolved_question=resolved_question,
        resolved_slots=resolved_slots,
        category=category,
        confidence=confidence,
        is_follow_up=is_follow_up,
    )


def _missing_slots(slots: SupportSlots) -> List[SlotName]:
    mapping = {
        SlotName.DEPLOYMENT_METHOD: slots.deployment_method,
        SlotName.VERSION: slots.version,
        SlotName.ERROR_MESSAGE: slots.error_message,
        SlotName.ENVIRONMENT: slots.environment,
    }
    return [name for name, value in mapping.items() if not value]


def _needs_non_deployment_clarification(
    category: Category,
    resolved_question: str,
    resolved_slots: SupportSlots,
) -> bool:
    if category not in {Category.KNOWLEDGE_BASE, Category.INTEGRATION}:
        return False
    if not _is_problem_report_query(resolved_question):
        return False

    provided_diagnostic_fields = sum(
        1
        for value in (
            resolved_slots.deployment_method,
            resolved_slots.version,
            resolved_slots.error_message,
            resolved_slots.environment,
        )
        if value
    )
    return provided_diagnostic_fields < 2


def _is_problem_report_query(question: str) -> bool:
    normalized = question.lower()
    if any(phrase in normalized for phrase in GUIDANCE_QUERY_PHRASES):
        return False
    return any(phrase in normalized for phrase in PROBLEM_REPORT_PHRASES)


def _build_clarification_question(category: Category, missing_slots: List[SlotName]) -> str:
    slot_labels = {
        SlotName.DEPLOYMENT_METHOD: "deployment method",
        SlotName.VERSION: "Dify version",
        SlotName.ERROR_MESSAGE: "exact error message",
        SlotName.ENVIRONMENT: "environment",
    }
    requested = ", ".join(slot_labels[name] for name in missing_slots)
    return f"I need more context to answer this {category.value} question reliably. Please provide the {requested}."


def _build_ticket_summary(
    category: Category,
    evidence_count: int,
    top_score: float,
    missing_slots: List[SlotName],
    is_follow_up: bool,
) -> str:
    reasons: List[str] = []
    if missing_slots:
        reasons.append(
            "missing slots: " + ", ".join(slot.value for slot in missing_slots)
        )
    reasons.append(f"retrieval evidence count={evidence_count}")
    reasons.append(f"top score={top_score:.3f}")
    prefix = "Escalated after one clarification" if is_follow_up else "Escalated"
    return f"{prefix} for {category.value}: " + "; ".join(reasons) + "."


def _build_answer(results: List[SearchResult]) -> str:
    lines = ["Relevant Dify documentation excerpts:"]
    for result in results:
        title = result.title or result.source_url
        lines.append(f"- {title}: {_sanitize_snippet(result.snippet)}")
    return "\n".join(lines)


def _sanitize_snippet(snippet: str) -> str:
    sanitized = snippet.replace("[", "").replace("]", "")
    sanitized = re.sub(r"\s+", " ", sanitized)
    return sanitized.strip()
def _retrieve_evidence(
    question: str,
    category: Category,
    manifest: SourceManifest,
    settings: Settings,
) -> tuple[str, List[SearchResult]]:
    allowed_pages = [page for page in manifest.pages if page.category == category.value]
    backend, results = search_index(
        query=question,
        top_k=settings.support_retrieval_top_k,
        sqlite_path=settings.sqlite_path,
        snapshot_version=manifest.snapshot_version,
        allowed_source_urls=[page.url for page in allowed_pages],
    )
    boosted = _apply_tag_boost(results=results, pages=allowed_pages, question=question)
    return backend, boosted


def _apply_tag_boost(results: List[SearchResult], pages: List[SourcePage], question: str) -> List[SearchResult]:
    if not results:
        return results
    query_terms = set(_normalized_terms(question))
    tags_by_url = {
        page.url: _normalized_terms(" ".join(page.tags))
        for page in pages
    }
    boosted_results: List[SearchResult] = []
    for result in results:
        matching_tags = query_terms.intersection(tags_by_url.get(result.source_url, []))
        boosted_results.append(
            SearchResult(
                chunk_id=result.chunk_id,
                source_url=result.source_url,
                snapshot_version=result.snapshot_version,
                title=result.title,
                chunk_index=result.chunk_index,
                score=result.score + 0.2 * len(matching_tags),
                snippet=result.snippet,
            )
        )
    boosted_results.sort(key=lambda item: (-item.score, item.source_url, item.chunk_index))
    return boosted_results


def _normalized_terms(value: str) -> List[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return [term for term in normalized.split() if term]


@lru_cache(maxsize=1)
def _load_manifest(source_manifest_path: str) -> SourceManifest:
    return load_source_manifest(Path(source_manifest_path))
