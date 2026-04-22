from app.core.config import get_settings


def test_answered_path_uses_llm_synthesis_when_enabled(support_client, monkeypatch):
    client, _ = support_client
    from app.support import service as support_service

    def _fake_synthesis(question, citations, settings):
        assert "chunk settings" in question.lower()
        assert citations
        return "Use the chunk settings screen in Dify to adjust chunk mode and separators."

    monkeypatch.setenv("COPILOT_ANSWER_SYNTHESIS_MODE", "llm")
    monkeypatch.setenv("COPILOT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("COPILOT_LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("COPILOT_LLM_MODEL", "fake-model")
    get_settings.cache_clear()
    monkeypatch.setattr(support_service, "synthesize_grounded_answer", _fake_synthesis)

    response = client.post(
        "/v1/support/ask",
        json={"question": "How do I configure chunk settings for a knowledge base in Dify?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "answered"
    assert payload["answer_generation_mode"] == "llm"
    assert payload["answer"].startswith("Use the chunk settings screen")
    assert payload["citations"]
    assert any("OpenAI-compatible LLM synthesis" in note for note in payload["notes"])

    get_settings.cache_clear()


def test_answered_path_falls_back_when_llm_call_fails(support_client, monkeypatch):
    client, _ = support_client
    from app.llm.client import LLMClientError
    from app.support import service as support_service

    def _failing_synthesis(question, citations, settings):
        raise LLMClientError("network timeout")

    monkeypatch.setenv("COPILOT_ANSWER_SYNTHESIS_MODE", "llm")
    monkeypatch.setenv("COPILOT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("COPILOT_LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("COPILOT_LLM_MODEL", "fake-model")
    get_settings.cache_clear()
    monkeypatch.setattr(support_service, "synthesize_grounded_answer", _failing_synthesis)

    response = client.post(
        "/v1/support/ask",
        json={"question": "How do I configure chunk settings for a knowledge base in Dify?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "answered"
    assert payload["answer_generation_mode"] == "deterministic_fallback"
    assert payload["answer"].startswith("Relevant Dify documentation excerpts:")
    assert any("deterministic fallback was used" in note for note in payload["notes"])

    get_settings.cache_clear()


def test_answered_path_auto_mode_without_llm_config_uses_deterministic(support_client, monkeypatch):
    client, _ = support_client
    from app.support import service as support_service

    def _unexpected_synthesis(*args, **kwargs):
        raise AssertionError("LLM synthesis should not be called without configuration in auto mode")

    monkeypatch.setenv("COPILOT_ANSWER_SYNTHESIS_MODE", "auto")
    monkeypatch.delenv("COPILOT_LLM_API_KEY", raising=False)
    monkeypatch.delenv("COPILOT_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("COPILOT_LLM_MODEL", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(support_service, "synthesize_grounded_answer", _unexpected_synthesis)

    response = client.post(
        "/v1/support/ask",
        json={"question": "How do I configure chunk settings for a knowledge base in Dify?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "answered"
    assert payload["answer_generation_mode"] == "deterministic"
    assert payload["answer"].startswith("Relevant Dify documentation excerpts:")
    assert any("deterministic answer assembly was used" in note for note in payload["notes"])

    get_settings.cache_clear()


def test_clarification_and_ticket_paths_do_not_call_llm(support_client, monkeypatch):
    client, _ = support_client
    from app.support import service as support_service

    def _unexpected_synthesis(*args, **kwargs):
        raise AssertionError("LLM synthesis should not be called outside answered path")

    monkeypatch.setenv("COPILOT_ANSWER_SYNTHESIS_MODE", "llm")
    monkeypatch.setenv("COPILOT_LLM_API_KEY", "test-key")
    monkeypatch.setenv("COPILOT_LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("COPILOT_LLM_MODEL", "fake-model")
    get_settings.cache_clear()
    monkeypatch.setattr(support_service, "synthesize_grounded_answer", _unexpected_synthesis)

    clarification = client.post(
        "/v1/support/ask",
        json={"question": "My plugin integration fails."},
    )
    assert clarification.status_code == 200
    clarification_payload = clarification.json()
    assert clarification_payload["run"]["status"] == "needs_clarification"
    assert clarification_payload["answer_generation_mode"] is None

    ticket = client.post(
        "/v1/support/ask",
        json={
            "question": "Still failing after I retried the integration.",
            "follow_up_run_id": clarification_payload["run"]["run_id"],
        },
    )
    assert ticket.status_code == 200
    ticket_payload = ticket.json()
    assert ticket_payload["run"]["status"] == "ticket_created"
    assert ticket_payload["answer_generation_mode"] is None

    get_settings.cache_clear()
