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

## 2.3 Day 4 Scope

This round adds only the minimum synchronous support decision chain:

- deterministic classification
- fixed-schema slot extraction
- manifest-guided retrieval
- deterministic extractive answer generation
- clarification on first insufficient pass
- ticket creation on unclassified or still-insufficient follow-up
- retrieval hit logging

This round still does not add:

- remote LLM calls
- embeddings
- rerank
- async worker or queue
- new frontend or dashboard work

## 2.4 Day 5 Scope

This round adds only data-layer hardening:

- expand the official Dify corpus toward support and troubleshooting coverage
- record `requested_url` and `final_url` separately for document snapshots
- reject content drift inside the same `snapshot_version + requested_url`
- keep repeated same-content fetches idempotent

This round still does not add:

- remote LLM calls
- embeddings
- rerank
- a full historical snapshot version management system
- changes to the Day 4 support decision rules

## 2.5 Day 6 Scope

This round adds only replay evaluation and threshold review:

- tracked support replay cases
- a repo-local replay eval runner
- preflight validation against the current local corpus
- replay-based review of the `MIN_SCORE` threshold

This round still does not add:

- remote LLM calls
- new product capabilities
- a full experiment tracking system
- online evaluation infrastructure
- changes to the Day 4 support API contract

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

## 6. V1 Target Model Boundaries

The following subsections describe the intended V1 product boundary. They are not a claim that the current Day 4 implementation already calls remote models.

### 6.1 Classification

- Target state uses structured model output
- Allowed output only:
  - `deployment`
  - `configuration`
  - `knowledge-base`
  - `integration`
  - `unclassified`

### 6.2 Slot Extraction

- Rules first
- Model assistance is optional
- Final output must conform to a fixed schema
- Allowed slots only:
  - `deployment_method`
  - `version`
  - `error_message`
  - `environment`

### 6.3 Retrieval

- Pure retrieval step
- No model participates in retrieval decisions
- Retrieval backend is described only as a `lightweight local vector store`

### 6.4 Answer Generation

- Target state may use model-generated answers only from retrieved evidence
- Citations are mandatory when evidence is returned

### 6.5 Clarification Question

- Target state may turn missing fields into natural language
- Only one clarification question is allowed

### 6.6 Ticket Creation

- Structured action only
- No free-form long-form generation requirement
- Must persist a structured record into SQLite

### 6.7 Current Day 4 Implementation

- `classification`: deterministic baseline rules, no remote model call
- `slot extraction`: deterministic fixed-schema extraction, no remote model call
- `retrieval`: local retrieval over indexed chunks
- `answer generation`: retrieval-backed extractive assembly, not remote-model generation
- `clarification question`: rules-generated text, not remote-model generation
- `ticket creation`: structured SQLite write

## 7. Retrieval and Threshold Rules

- `MIN_EVIDENCE_HITS = 2`
- `MIN_SCORE` is a configurable threshold
- Day 6 replay sweep reviewed `MIN_SCORE` at:
  - `0.20`
  - `0.25`
  - `0.30`
  - `0.35`
  - `0.40`
  - `0.45`
- The replay sweep did not produce a safer or more accurate alternative to the current default
- The default `MIN_SCORE` therefore remains `0.35`
- This is a replay-calibrated local baseline, not a claim of production-grade threshold tuning

## 8. Data Model Requirements

SQLite is used for tickets, logs, and metadata.

Required Day 1 entities:

- `support_runs`
- `retrieval_hits`
- `tickets`
- `document_snapshots`

### 8.1 Document Snapshot Fields

Each snapshot record must support:

- `requested_url`
- `final_url`
- `source_url`
- `fetched_at`
- `content_hash`
- `snapshot_version`

Current runtime note:

- `source_url` is retained as a compatibility alias of `requested_url` for retrieval and existing response shapes

### 8.2 Snapshot Version Rule

For Day 1, `snapshot_version` is a manifest-level stable identifier stored in `data/sources.yaml`.

Current convention:

- `dify-docs-en-2026-04-21-v2`

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
- generate stable, reproducible `snapshot_id` values from `requested_url + snapshot_version`
- repeated runs for the same `requested_url + snapshot_version` must update the same logical snapshot record rather than creating uncontrolled duplicates

### 8.4 Day 3 Chunk and Retrieval Rules

- chunking must be deterministic and reproducible
- chunk ids must be stable for the same `snapshot_version + source_url + chunk_index`
- repeated indexing for the same snapshot version must not create uncontrolled duplicate chunk rows
- Day 3 retrieval is a minimal local retrieval step implemented with SQLite FTS5 when available
- if SQLite FTS5 is unavailable, retrieval may fall back to a repository-local lexical implementation without introducing heavyweight frameworks

### 8.5 Snapshot Version Limitation

- `snapshot_version` is still a manifest or batch label
- it is not yet a full historical or content-immutable snapshot versioning system
- this limitation remains known after Day 5

### 8.6 Day 5 Snapshot Hardening Rules

- store `requested_url` and `final_url` separately
- if there is no redirect, `final_url = requested_url`
- for the same `snapshot_version + requested_url`:
  - if `content_hash` is unchanged, allow idempotent update
- if `content_hash` changes, reject the write explicitly
- do not silently overwrite changed content inside the same snapshot version label

### 8.7 Day 6 Replay Eval Rules

- replay eval cases are tracked in source control
- replay eval must run against the current local Dify corpus for the current manifest snapshot version
- replay eval must fail fast when snapshots or chunks are missing
- replay eval must reuse the current support decision chain instead of mocking its outputs
- replay eval is a local reproducible behavior baseline, not a replacement for engineering tests

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
- run the synchronous support decision chain
- persist `support_runs`, and when applicable `retrieval_hits` and `tickets`

Day 1 behavior:

- scaffold only
- no real classification
- no retrieval
- no answer generation
- no clarification logic
- no ticket creation logic

Day 4 behavior:

- synchronous `200` response
- deterministic baseline classification
- fixed-schema slot extraction
- manifest-guided retrieval
- retrieval-backed extractive answer assembly
- rules-generated clarification text
- returns one of:
  - `answered`
  - `needs_clarification`
  - `ticket_created`
- writes retrieval hits when retrieval is executed
- creates a ticket record when escalation is required

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

Current Day 4 continuation field:

- `SupportAskRequest.follow_up_run_id` may reference one prior clarification run so the second insufficient pass escalates to ticket creation instead of looping clarification

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
