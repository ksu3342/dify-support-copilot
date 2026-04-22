from __future__ import annotations

from typing import List

import httpx

from app.core.config import Settings
from app.models.api import Citation


class LLMClientError(RuntimeError):
    pass


def is_llm_configured(settings: Settings) -> bool:
    return all(
        value.strip()
        for value in (
            settings.llm_api_key,
            settings.llm_base_url,
            settings.llm_model,
        )
    )


def synthesize_grounded_answer(
    question: str,
    citations: List[Citation],
    settings: Settings,
) -> str:
    if not is_llm_configured(settings):
        raise LLMClientError("LLM configuration is incomplete.")

    payload = {
        "model": settings.llm_model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are answering an internal Dify support question. "
                    "Use only the provided evidence snippets. "
                    "Be concise, practical, and avoid unsupported claims. "
                    "If the evidence is incomplete, stay narrow and describe only what the evidence supports."
                ),
            },
            {
                "role": "user",
                "content": _build_user_prompt(question=question, citations=citations),
            },
        ],
    }

    request_url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(request_url, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMClientError(f"LLM request failed: {exc.__class__.__name__}.") from exc

    try:
        content = _extract_message_content(response.json())
    except (KeyError, TypeError, ValueError) as exc:
        raise LLMClientError("LLM response payload was missing a usable answer.") from exc

    if not content:
        raise LLMClientError("LLM response payload was empty.")
    return content


def _build_user_prompt(question: str, citations: List[Citation]) -> str:
    evidence_lines = []
    for index, citation in enumerate(citations, start=1):
        title = citation.title or citation.source_url
        evidence_lines.append(
            f"[{index}] title: {title}\n"
            f"source_url: {citation.source_url}\n"
            f"snippet: {citation.snippet}"
        )

    evidence_block = "\n\n".join(evidence_lines)
    return (
        f"Question:\n{question}\n\n"
        f"Evidence:\n{evidence_block}\n\n"
        "Write a short grounded answer. Do not invent steps or facts beyond the evidence."
    )


def _extract_message_content(payload: dict) -> str:
    choices = payload["choices"]
    if not choices:
        raise ValueError("missing choices")

    message = choices[0]["message"]
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            str(item.get("text", "")).strip()
            for item in content
            if isinstance(item, dict) and item.get("type") in {None, "text"}
        ]
        return "\n".join(part for part in parts if part).strip()
    raise ValueError("unsupported message content")
