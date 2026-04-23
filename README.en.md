# Dify Internal Support Copilot

[中文](./README.md) | [Legacy Chinese entry](./README.zh-CN.md)

Evidence-grounded support triage backend for self-hosted Dify operations.

Self-hosted Dify support questions often span installation, configuration, knowledge base setup, plugins, and API integration docs. This project turns those requests into a runnable backend flow: collect evidence from official docs, classify the question, retrieve relevant passages, and route the request to `answered`, `needs_clarification`, or `ticket_created`.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\fetch_sources.py
.\.venv\Scripts\python scripts\build_index.py
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/readyz'
```

`/healthz` is only a liveness check. `/readyz` indicates whether the local Dify document snapshot and chunk index are ready for support answering.

## How One Support Request Is Handled

The sample below comes from a local API verification against the current repository. It is not a hand-written ideal response.

**Question**

```text
How do I configure chunk settings for a knowledge base in Dify?
```

**Classification**

```json
{
  "status": "answered",
  "category": "knowledge-base",
  "answer_generation_mode": "deterministic"
}
```

**Retrieved evidence**

```json
[
  {
    "chunk_id": "chunk_0a2e3366da743c0b1403aaee",
    "source_url": "https://docs.dify.ai/en/guides/knowledge-base/create-knowledge-and-upload-documents/chunking-and-cleaning-text",
    "snapshot_version": "dify-docs-en-2026-04-21-v2",
    "title": "Configure the Chunk Settings - Dify Docs",
    "chunk_index": 1
  },
  {
    "chunk_id": "chunk_1ddcceb284436856cbeaec27",
    "source_url": "https://docs.dify.ai/en/use-dify/knowledge/create-knowledge/setting-indexing-methods",
    "snapshot_version": "dify-docs-en-2026-04-21-v2",
    "title": "Specify the Index Method and Retrieval Settings - Dify Docs",
    "chunk_index": 8
  }
]
```

**Answer snippet**

```text
Relevant Dify documentation excerpts:
- Configure the Chunk Settings - Dify Docs: ... a Chunk Mode The chunk mode cannot be changed once the knowledge base is created. However, chunk settings ...
- Specify the Index Method and Retrieval Settings - Dify Docs: ... Utilizing embedding models, even if the exact terms from the query do not appear in the knowledge base ...
```

The other two outcome paths are covered by integration tests as well:

- `My plugin integration fails.` -> `needs_clarification`
- `Still failing after I retried the integration.` with `follow_up_run_id` -> `ticket_created`

## What This Repo Does

This repository is not a general-purpose chatbot. It turns self-hosted Dify support requests into an inspectable backend baseline:

- fetch, clean, and persist local snapshots from official Dify English docs
- use manifest metadata for category-guided retrieval
- classify support questions into a fixed category set
- answer with citations when evidence is sufficient
- ask for one clarification when information is missing
- create a local ticket when the request remains insufficient or cannot be classified
- log runs, retrieval hits, tickets, and snapshot metadata
- replay support cases through a local eval runner

## What Is Implemented

- Dify official document ingestion, cleaning, and snapshot persistence
- snapshot drift rejection within the same `snapshot_version`
- deterministic classification for `deployment`, `configuration`, `knowledge-base`, `integration`, and `unclassified`
- fixed-slot extraction for `deployment_method`, `version`, `error_message`, and `environment`
- manifest-guided local retrieval
- synchronous `POST /v1/support/ask` outcomes: `answered`, `needs_clarification`, or `ticket_created`
- `retrieval_hits` logging and SQLite ticket persistence
- liveness/readiness separation through `GET /healthz` and `GET /readyz`
- replay eval runner with version-controlled eval cases
- optional OpenAI-compatible answer synthesis on the `answered` path
- deterministic fallback when the provider fails or is rate-limited

## How The Runtime Decides

```text
support question
  -> deterministic classification
  -> fixed-slot extraction
  -> manifest-guided retrieval
  -> decision
       -> answered + citations
       -> needs_clarification
       -> ticket_created
  -> support_runs / retrieval_hits / tickets
```

Key rules:

- `unclassified` goes directly to `ticket_created`
- deployment and configuration requests with insufficient slots go to `needs_clarification`
- vague knowledge-base or integration issue reports clarify first instead of answering just because retrieval found hits
- only one clarification turn is allowed; a still-insufficient follow-up escalates to a ticket
- `/v1/support/ask` does not fetch docs or build the index on the request path; readiness must be prepared by the ingest/index commands

## Engineering Evidence

These repository entry points back the current claims:

- API entry, `/healthz`, and `/readyz`: [`app/api/main.py`](./app/api/main.py)
- support decision flow: [`app/support/service.py`](./app/support/service.py)
- optional LLM answer synthesis client: [`app/llm/client.py`](./app/llm/client.py)
- ingestion, cleaning, and snapshot handling: [`app/ingest/`](./app/ingest/)
- chunking, indexing, and local retrieval: [`app/retrieval/`](./app/retrieval/)
- SQLite schema: [`scripts/init_db.sql`](./scripts/init_db.sql)
- support API integration tests: [`tests/integration/`](./tests/integration/)
- replay eval runner: [`scripts/run_eval.py`](./scripts/run_eval.py)
- eval cases: [`data/evals/support_eval_v1.yaml`](./data/evals/support_eval_v1.yaml)
- demo script: [`docs/DEMO_SCRIPT.md`](./docs/DEMO_SCRIPT.md)
- architecture notes: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)

## Optional LLM Answer Synthesis

The `answered` path includes an optional OpenAI-compatible answer synthesis hook. It is only attempted after retrieval evidence is already sufficient and the request has already been routed to `answered`.

Current constraints:

- classification remains deterministic
- clarification and ticket decisions do not call the LLM
- citations still come from retrieval hits
- a successful provider call may return `answer_generation_mode = llm`
- provider failure, timeout, or rate limiting falls back to `answer_generation_mode = deterministic_fallback`
- this repository does not claim that the live provider path is stably verified

This should be read as a switchable answer-generation enhancement, not as a complete LLM Copilot or agent orchestration runtime.

## Boundaries / Non-goals

This repository is an AI application prototype / Python backend service for a self-hosted Dify support triage baseline.

It does not implement:

- a complete support platform for production deployment
- a frontend or dashboard
- orchestration across multiple autonomous agents
- async workers or queues
- embedding-based retrieval or vector database benchmarking
- a complex permission system
- a stably verified live LLM provider path

Those boundaries are deliberate. The current priority is a runnable, inspectable, testable, replay-evaluable support flow rather than a platform.

## Further Reading

- [Demo Script](./docs/DEMO_SCRIPT.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Interview Notes](./docs/INTERVIEW_NOTES.md)
- [Resume Bullets](./docs/RESUME_BULLETS.md)
- [Specification](./SPEC.md)
