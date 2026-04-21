import sqlite3


def test_support_follow_up_escalates_to_ticket_and_ticket_can_be_read(support_client):
    client, db_path = support_client

    first_response = client.post(
        "/v1/support/ask",
        json={"question": "My docker compose deployment fails during install."},
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    assert first_payload["run"]["status"] == "needs_clarification"

    follow_up_response = client.post(
        "/v1/support/ask",
        json={
            "question": "Still failing after retry.",
            "follow_up_run_id": first_payload["run"]["run_id"],
        },
    )

    assert follow_up_response.status_code == 200
    payload = follow_up_response.json()
    assert payload["run"]["status"] == "ticket_created"
    assert payload["ticket"] is not None

    ticket_id = payload["ticket"]["ticket_id"]
    ticket_response = client.get(f"/v1/tickets/{ticket_id}")
    assert ticket_response.status_code == 200
    assert ticket_response.json()["summary"]

    connection = sqlite3.connect(db_path)
    try:
        ticket_count = connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        hit_count = connection.execute(
            "SELECT COUNT(*) FROM retrieval_hits WHERE run_id = ?",
            (payload["run"]["run_id"],),
        ).fetchone()[0]
    finally:
        connection.close()

    assert ticket_count == 1
    assert hit_count > 0
