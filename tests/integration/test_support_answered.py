import sqlite3


def test_support_ask_answered_returns_grounded_citations(support_client):
    client, db_path = support_client

    response = client.post(
        "/v1/support/ask",
        json={"question": "How do I configure chunk settings for a knowledge base in Dify?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "answered"
    assert payload["run"]["category"] == "knowledge-base"
    assert payload["answer"]
    assert payload["answer_generation_mode"] == "deterministic"
    assert payload["citations"]
    assert any("chunking-and-cleaning-text" in citation["source_url"] for citation in payload["citations"])

    connection = sqlite3.connect(db_path)
    try:
        hit_count = connection.execute(
            "SELECT COUNT(*) FROM retrieval_hits WHERE run_id = ?",
            (payload["run"]["run_id"],),
        ).fetchone()[0]
    finally:
        connection.close()

    assert hit_count > 0
