import sqlite3


def test_support_ask_needs_clarification_when_deployment_slots_are_missing(support_client):
    client, db_path = support_client

    response = client.post(
        "/v1/support/ask",
        json={"question": "My docker compose deployment fails during install."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "needs_clarification"
    assert payload["run"]["category"] == "deployment"
    assert payload["clarification"] is not None
    assert payload["clarification"]["question"]
    assert payload["clarification"]["missing_slots"]
    assert "version" in payload["clarification"]["missing_slots"]
    assert "environment" in payload["clarification"]["missing_slots"]

    connection = sqlite3.connect(db_path)
    try:
        hit_count = connection.execute(
            "SELECT COUNT(*) FROM retrieval_hits WHERE run_id = ?",
            (payload["run"]["run_id"],),
        ).fetchone()[0]
    finally:
        connection.close()

    assert hit_count > 0
