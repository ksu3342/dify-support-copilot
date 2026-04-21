# SPEC

## 1. Product Definition

`Dify Internal Support Copilot` is an internal support triage assistant for self-hosted Dify usage and maintenance scenarios.

It is not:

- a platform
- a generic agent demo
- a frontend product
- a generalized knowledge assistant

## 2. Frozen Day 1 Scope

This round delivers:

- independent repository bootstrap
- written scope and interface contract
- FastAPI service scaffold
- initial SQLite schema
- source manifest for Dify docs
- minimal health test

This round does not deliver:

- real crawling
- real retrieval
- real LLM calls
- real ticket routing logic
- full production behavior

## 2.1 Day 2 Scope

This round adds only the document ingestion minimum loop:

- load `data/sources.yaml`
- fetch official Dify documentation pages over HTTP
- persist raw HTML snapshots
- derive cleaned text
- upsert snapshot metadata into `document_snapshots`

This round still does not add:

- retrieval
- chunking
- embeddings
- vector store writes
- LLM calls
- citation generation
- clarification logic
- ticket creation business logic
- new API endpoints

## 2.2 Day 3 Scope

This round adds only the minimum local retrieval loop:

- read cleaned text from `data/clean/<snapshot_version>/...`
- create deterministic chunks
- persist chunk metadata into SQLite
- build a minimal local retrieval index
- expose CLI-only search over indexed chunks

This round still does not add:

- LLM calls
- classification
- answer generation
- citation assembly APIs
- clarification logic
- ticket business logic
- external embedding services
- multi-vector-store support

## 3. Frozen V1 Main Chain

1. User asks a question
2. Classify the request
3. Retrieve from official Dify documentation
4. Generate answer with citations
5. Ask one clarification question if needed
6. If still insufficient, execute `create_ticket`
7. Persist logs

The only real action in V1 is `create_ticket`.

## 4. Business Categories

Allowed business categories:

- `deployment`
- `configuration`
- `knowledge-base`
- `integration`

Fallback status:

- `unclassified`

`unclassified` is not a fifth business domain. It exists to avoid forced classification for low-confidence, out-of-scope, multi-intent, or unstable cases.

## 5. Corpus Constraints

- Single corpus domain: `Dify`
- Official sources only
- Primary authority: English pages on `docs.dify.ai`
- Chinese auto-translated pages are not authoritative evidence
- No secondary blogs as core knowledge
- No forum content as core knowledge
- No self-authored FAQ injected into the knowledge base
- GitHub issue phrasing may be used for future evaluation prompts, but issue content must not be ingested back into the knowledge base

## 6. LLM Boundaries

### 6.1 Classification

- Uses LLM with structured output
- Allowed output only:
  - `deployment`
  - `configuration`
  - `knowledge-base`
  - `integration`
  - `unclassified`

### 6.2 Slot Extraction

- Rules first
- LLM assistance is optional
- Final output must conform to a fixed schema
- Allowed slots only:
  - `deployment_method`
  - `version`
  - `error_message`
  - `environment`

### 6.3 Retrieval

- Pure retrieval step
- No LLM participates in retrieval decisions
- Retrieval backend is described only as a `lightweight local vector store`

### 6.4 Answer Generation

- LLM may answer only from retrieved evidence
- Citations are mandatory in the final answer when evidence is returned

### 6.5 Clarification Question

- LLM may turn missing fields into natural language
- Only one clarification question is allowed

### 6.6 Ticket Creation

- Structured action only
- No free-form long-form generation requirement
- Must persist a structured record into SQLite

## 7. Retrieval and Threshold Rules

- `MIN_EVIDENCE_HITS = 2`
- `MIN_SCORE` is a configurable threshold
- Any default `MIN_SCORE` value before Day 6 replay evaluation is placeholder-only and must be treated as `pending calibration`

## 8. Data Model Requirements

SQLite is used for tickets, logs, and metadata.

Required Day 1 entities:

- `support_runs`
- `retrieval_hits`
- `tickets`
- `document_snapshots`

### 8.1 Document Snapshot Fields

Each snapshot record must support:

- `source_url`
- `fetched_at`
- `content_hash`
- `snapshot_version`

### 8.2 Snapshot Version Rule

For Day 1, `snapshot_version` is a manifest-level stable identifier stored in `data/sources.yaml`.

Current convention:

- `dify-docs-en-2026-04-21-v1`

Rule:

- stable for the same source manifest version
- manually bumpable when the manifest or capture procedure changes
- reproducible because it is explicitly versioned in source control

### 8.3 Day 2 Ingestion Rules

- only fetch URLs listed in `data/sources.yaml`
- only allow `docs.dify.ai` as the authoritative host
- use ordinary HTTP fetching, not browser automation
- store raw HTML under `data/raw/<snapshot_version>/...`
- store cleaned text under `data/clean/<snapshot_version>/...`
- generate stable, reproducible `snapshot_id` values from `source_url + snapshot_version`
- repeated runs for the same `source_url + snapshot_version` must update the same logical snapshot record rather than creating uncontrolled duplicates

### 8.4 Day 3 Chunk and Retrieval Rules

- chunking must be deterministic and reproducible
- chunk ids must be stable for the same `snapshot_version + source_url + chunk_index`
- repeated indexing for the same snapshot version must not create uncontrolled duplicate chunk rows
- Day 3 retrieval is a minimal local retrieval step implemented with SQLite FTS5 when available
- if SQLite FTS5 is unavailable, retrieval may fall back to a repository-local lexical implementation without introducing heavyweight frameworks

## 9. API Contract

### 9.1 `GET /healthz`

Purpose:

- process health check
- SQLite readiness check

Day 1 behavior:

- implemented

### 9.2 `POST /v1/support/ask`

Purpose:

- validate request payload
- persist a `support_runs` record
- return a scaffold response shape compatible with the future chain

Day 1 behavior:

- scaffold only
- no real classification
- no retrieval
- no answer generation
- no clarification logic
- no ticket creation logic

### 9.3 `GET /v1/runs/{run_id}`

Purpose:

- retrieve persisted run metadata

Day 1 behavior:

- implemented for stored scaffold runs

### 9.4 `GET /v1/tickets/{ticket_id}`

Purpose:

- retrieve a persisted ticket record

Day 1 behavior:

- read-only scaffold endpoint
- no ticket is created automatically in Day 1

## 10. Request and Response Schema Requirements

Day 1 API models must include at minimum:

- `SupportAskRequest`
- `SupportAskResponse`
- `Citation`
- `TicketRecord`
- `RunRecord`
- `SnapshotRecord`

Slot schema must explicitly represent:

- `deployment_method`
- `version`
- `error_message`
- `environment`

## 11. Frozen Out of Scope

- memory
- MCP
- dashboard
- rerank
- multi-model support
- multi-vector-store support
- frontend UI
- canvas workflow
- multi-agent orchestration
- async worker or queue
- platformization
- complex RBAC
- reuse of unrelated testing business semantics
- anything that looks more advanced but is outside the frozen V1 chain
