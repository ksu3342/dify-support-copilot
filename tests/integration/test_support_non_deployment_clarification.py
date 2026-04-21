import sqlite3


def test_support_ask_kb_vague_complaint_needs_clarification(support_client):
    client, db_path = support_client

    response = client.post(
        "/v1/support/ask",
        json={"question": "My uploaded documents are not searchable."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "needs_clarification"
    assert payload["run"]["category"] == "knowledge-base"
    assert payload["clarification"] is not None
    assert payload["clarification"]["missing_slots"] == [
        "deployment_method",
        "version",
        "error_message",
        "environment",
    ]

    connection = sqlite3.connect(db_path)
    try:
        hit_count = connection.execute(
            "SELECT COUNT(*) FROM retrieval_hits WHERE run_id = ?",
            (payload["run"]["run_id"],),
        ).fetchone()[0]
    finally:
        connection.close()

    assert hit_count > 0


def test_support_follow_up_kb_vague_complaint_escalates_to_ticket(support_client):
    client, db_path = support_client

    first_response = client.post(
        "/v1/support/ask",
        json={"question": "My knowledge base search is bad."},
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["run"]["status"] == "needs_clarification"

    follow_up_response = client.post(
        "/v1/support/ask",
        json={
            "question": "Still bad after rebuilding the knowledge base.",
            "follow_up_run_id": first_payload["run"]["run_id"],
        },
    )

    assert follow_up_response.status_code == 200
    payload = follow_up_response.json()
    assert payload["run"]["status"] == "ticket_created"
    assert payload["ticket"] is not None

    connection = sqlite3.connect(db_path)
    try:
        ticket_count = connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    finally:
        connection.close()

    assert ticket_count == 1


def test_support_ask_integration_vague_complaint_needs_clarification(support_client):
    client, db_path = support_client

    response = client.post(
        "/v1/support/ask",
        json={"question": "My API integration is broken."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "needs_clarification"
    assert payload["run"]["category"] == "integration"
    assert payload["clarification"] is not None
    assert payload["clarification"]["missing_slots"] == [
        "deployment_method",
        "version",
        "error_message",
        "environment",
    ]

    connection = sqlite3.connect(db_path)
    try:
        hit_count = connection.execute(
            "SELECT COUNT(*) FROM retrieval_hits WHERE run_id = ?",
            (payload["run"]["run_id"],),
        ).fetchone()[0]
    finally:
        connection.close()

    assert hit_count > 0


def test_support_follow_up_integration_vague_complaint_escalates_to_ticket(support_client):
    client, db_path = support_client

    first_response = client.post(
        "/v1/support/ask",
        json={"question": "My plugin integration fails."},
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["run"]["status"] == "needs_clarification"
    assert first_payload["clarification"]["missing_slots"] == [
        "deployment_method",
        "version",
        "environment",
    ]

    follow_up_response = client.post(
        "/v1/support/ask",
        json={
            "question": "Still failing after I retried the integration.",
            "follow_up_run_id": first_payload["run"]["run_id"],
        },
    )

    assert follow_up_response.status_code == 200
    payload = follow_up_response.json()
    assert payload["run"]["status"] == "ticket_created"
    assert payload["ticket"] is not None

    connection = sqlite3.connect(db_path)
    try:
        ticket_count = connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    finally:
        connection.close()

    assert ticket_count == 1
