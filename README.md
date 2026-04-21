# Dify Internal Support Copilot

An internal support copilot for self-hosted Dify deployment and maintenance questions.

## What This Repo Is

- A single-purpose internal support triage assistant for self-hosted Dify.
- A single-corpus system constrained to authoritative Dify documentation.
- A minimal FastAPI service with a synchronous SQLite-backed support decision chain and local retrieval.

## What This Repo Is Not

- Not a general agent platform.
- Not a dashboard product.
- Not a generic RAG demo.
- Not a multi-agent, multi-model, or multi-vector-store system.

## V1 Target Scope

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

## V1 Target Model Boundaries

This is the intended V1 product boundary, not a claim that the current code already uses remote LLMs.

- `classification`: target is structured model output restricted to `deployment`, `configuration`, `knowledge-base`, `integration`, `unclassified`
- `slot extraction`: target is rules first with optional model assist, fixed schema only:
  - `deployment_method`
  - `version`
  - `error_message`
  - `environment`
- `retrieval`: retrieval only, no model in retrieval decision
- `answer generation`: target is evidence-grounded answer generation with citations
- `clarification question`: target is one natural-language clarification question when required
- `ticket creation`: structured action only, persisted to SQLite

## Current Day 4 Runtime

The current checked-in implementation is a deterministic baseline, not a remote-model system.

- `classification`: deterministic keyword and weighting rules
- `slot extraction`: deterministic fixed-schema extraction
- `retrieval`: local retrieval using the current indexed Dify corpus
- `answer generation`: retrieval-backed extractive assembly from evidence snippets
- `clarification question`: rule-generated clarification text
- `ticket creation`: structured SQLite write
- `snapshot_version`: still a manifest or batch label, not an immutable content snapshot identifier

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

## Day 4 Delivery

Implemented in this round:

- `POST /v1/support/ask` now runs a real synchronous support chain and returns `200`
- Deterministic baseline classification
- Fixed-schema slot extraction for:
  - `deployment_method`
  - `version`
  - `error_message`
  - `environment`
- Manifest-guided retrieval using category filtering and light tag-based score boost
- Deterministic retrieval-backed extractive answers with citations
- Clarification flow with one-step continuation via `follow_up_run_id`
- Real ticket creation in SQLite when the request is unclassified or still insufficient after clarification
- Retrieval hit logging into `retrieval_hits`
- Clarification text is rule-generated, not remote-model generated
- Answer assembly is retrieval-backed and extractive, not remote-model generated

Still not implemented in this round:

- remote LLM classification
- remote LLM answer generation
- rerank
- embeddings
- async worker or queue

Current limitation:

- `snapshot_version` is still a manifest or batch label. It is not yet a content-immutable snapshot version.

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
- `http://127.0.0.1:8000/docs`

Example support request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/support/ask -ContentType 'application/json' -Body '{"question":"How do I configure chunk settings for a knowledge base in Dify?"}'
```

## Test

```powershell
cd D:\AI agent\dify-support-copilot
.venv\Scripts\python -m pytest
```

Integration tests are self-contained:

- they initialize a temporary SQLite database
- they seed tracked fixtures from `tests/fixtures/`
- they do not depend on `storage/copilot.db`
- they do not depend on existing `data/raw/` or `data/clean/` contents

## Docker

```powershell
cd D:\AI agent\dify-support-copilot
docker compose up --build
```

Docker persistence now mounts both:

- `./storage:/app/storage`
- `./data:/app/data`

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
