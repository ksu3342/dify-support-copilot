# Demo Script

This script is designed for a 3-5 minute Windows PowerShell demo of the current Day 7 baseline.

## Demo Goal

Show that the project is not just "ask docs":

- one query is answered with grounded citations
- one vague query triggers clarification instead of overconfident answering
- one follow-up still lacking enough context escalates to a ticket

## Preconditions

Run from `D:\AI agent\dify-support-copilot`.

The local corpus and index must already exist:

```powershell
.\.venv\Scripts\python scripts\fetch_sources.py
.\.venv\Scripts\python scripts\build_index.py
```

## 1. Start the API

Terminal A:

```powershell
cd D:\AI agent\dify-support-copilot
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Expected:

- FastAPI starts successfully
- `/healthz` returns `status = ok`

## 2. Verify the service is up

Terminal B:

```powershell
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/healthz' | ConvertTo-Json
```

Expected:

- `status = "ok"`
- `sqlite_ready = true`

## 3. Answered path

```powershell
$answered = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/support/ask' -ContentType 'application/json' -Body '{
  "question": "How do I configure chunk settings for a knowledge base in Dify?"
}'
$answered | ConvertTo-Json -Depth 6
```

What to point out:

- `run.status` is `answered`
- response includes non-empty `citations`
- answer text is grounded in retrieved docs, not generated from a remote model

## 4. Clarification path

```powershell
$clarify = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/support/ask' -ContentType 'application/json' -Body '{
  "question": "My plugin integration fails."
}'
$clarify | ConvertTo-Json -Depth 6
```

What to point out:

- classification is still `integration`
- the system does not answer too early
- `clarification.question` and `missing_slots` explain what is missing

## 5. Ticket path through one follow-up

```powershell
$followUpBody = @{
  question = "Still failing after I retried the integration."
  follow_up_run_id = $clarify.run.run_id
} | ConvertTo-Json

$ticket = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/v1/support/ask' -ContentType 'application/json' -Body $followUpBody
$ticket | ConvertTo-Json -Depth 6
```

What to point out:

- second turn does not loop clarification forever
- `run.status` becomes `ticket_created`
- `ticket.ticket_id` is returned immediately

## 6. Show the stored ticket

```powershell
Invoke-RestMethod -Method Get -Uri ("http://127.0.0.1:8000/v1/tickets/" + $ticket.ticket.ticket_id) | ConvertTo-Json -Depth 6
```

Expected:

- ticket is retrievable from SQLite
- `summary` explains why the request was escalated

## Optional Demo Close

If you want to show that behavior is evaluated, not hand-waved:

```powershell
.\.venv\Scripts\python scripts\run_eval.py
```

Callout:

- replay eval is local and reproducible
- it is used to catch rule regressions
- it is not being presented as an online eval platform
