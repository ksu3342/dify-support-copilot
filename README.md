# Dify Internal Support Copilot

Day 1 scaffold for an internal support copilot focused on self-hosted Dify deployment and maintenance questions.

## What This Repo Is

- A single-purpose internal support triage assistant for self-hosted Dify.
- A single-corpus system constrained to authoritative Dify documentation.
- A minimal FastAPI service with SQLite-backed run logging and placeholder API contracts.

## What This Repo Is Not

- Not a general agent platform.
- Not a dashboard product.
- Not a generic RAG demo.
- Not a multi-agent, multi-model, or multi-vector-store system.

## Frozen V1 Scope

- Single corpus domain: `Dify`
- Business categories:
  - `deployment`
  - `configuration`
  - `knowledge-base`
  - `integration`
- Fallback state: `unclassified`
- Single main chain:
  1. User asks a question
  2. Classify
  3. Retrieve from official Dify docs
  4. Answer with citations
  5. Ask one clarification question if information is missing
  6. If still insufficient, run the single real action: `create_ticket`
  7. Record logs

## LLM Boundaries

- `classification`: LLM with structured output only. Allowed labels: `deployment`, `configuration`, `knowledge-base`, `integration`, `unclassified`
- `slot extraction`: rules first, optional LLM assist, fixed schema only:
  - `deployment_method`
  - `version`
  - `error_message`
  - `environment`
- `retrieval`: retrieval only, no LLM in retrieval decision
- `answer generation`: LLM over retrieved evidence with citations
- `clarification question`: LLM may convert missing slots into a single natural-language question
- `ticket creation`: structured action only, persisted to SQLite

## Current Day 1 Delivery

Implemented in this round:

- Independent git repository at `D:\AI agent\dify-support-copilot`
- Frozen spec in `SPEC.md`
- FastAPI scaffold with:
  - `GET /healthz`
  - `POST /v1/support/ask`
  - `GET /v1/runs/{run_id}`
  - `GET /v1/tickets/{ticket_id}`
- SQLite schema for:
  - `support_runs`
  - `retrieval_hits`
  - `tickets`
  - `document_snapshots`
- Source manifest at `data/sources.yaml`
- Minimal pytest coverage for `/healthz`

Not implemented in this round:

- Real crawling or document snapshot ingestion
- Real chunking, indexing, or retrieval
- Real LLM integration
- Real clarification logic
- Real ticket decision logic
- Full end-to-end support chain

## Day 2 Delivery

Implemented in this round:

- Real source manifest loading from `data/sources.yaml`
- Real HTTP fetching for official `docs.dify.ai` pages listed in the manifest
- Raw HTML snapshots written under `data/raw/<snapshot_version>/...`
- Cleaned text written under `data/clean/<snapshot_version>/...`
- Idempotent snapshot metadata upsert into SQLite `document_snapshots`
- Minimal offline tests for:
  - source manifest loading
  - stable snapshot id and path generation
  - HTML cleaning

Still not implemented in this round:

- retrieval
- chunking
- embeddings
- vector search
- LLM integration
- citation generation
- clarification logic
- ticket business logic

## Day 3 Delivery

Implemented in this round:

- Deterministic chunking over cleaned text
- Minimal local retrieval index using SQLite FTS5
- Chunk metadata persisted in SQLite `document_chunks`
- CLI commands for index build and search:
  - `.\.venv\Scripts\python scripts\build_index.py`
  - `.\.venv\Scripts\python scripts\search_chunks.py --query "docker compose self hosted install" --top-k 5`

Still not implemented in this round:

- LLM-based classification
- citation answer generation
- clarification logic
- ticket business logic
- external embeddings or vector database integration

Run the Day 2 fetch command with:

```powershell
cd D:\AI agent\dify-support-copilot
.\.venv\Scripts\python scripts\fetch_sources.py
```

## Storage and Retrieval Notes

- SQLite is used for tickets, logs, and metadata.
- Retrieval is specified only as a `lightweight local vector store`.
- No specific vector store is treated as a product-level commitment in the spec.
- Day 3 local retrieval uses SQLite FTS5 as a minimal, repo-local indexing step. This is a bootstrap retrieval mechanism, not a claim that full RAG is complete.

## Threshold Notes

- `MIN_EVIDENCE_HITS = 2` is reserved in the spec.
- `MIN_SCORE` is configurable and marked as `pending calibration`.
- Any default value in config is a placeholder, not a validated constant.

## Document Snapshot Versioning

Every document snapshot record is expected to keep:

- `source_url`
- `fetched_at`
- `content_hash`
- `snapshot_version`

For Day 1, `snapshot_version` is sourced from `data/sources.yaml` and treated as a stable manifest version identifier. The actual fetch pipeline is out of scope for this round.

For Day 2, the same `snapshot_version` is used to place raw and cleaned files on disk and to key SQLite snapshot metadata updates.

## Local Run

```powershell
cd D:\AI agent\dify-support-copilot
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Then open:

- `http://127.0.0.1:8000/healthz`

## Test

```powershell
cd D:\AI agent\dify-support-copilot
.venv\Scripts\python -m pytest
```

## Docker

```powershell
cd D:\AI agent\dify-support-copilot
docker compose up --build
```

## Repo Layout

```text
app/
  api/
    main.py
    routes/
  core/
  models/
data/
scripts/
tests/
```
