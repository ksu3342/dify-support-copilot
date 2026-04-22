# Dify Internal Support Copilot

[简体中文](./README.zh-CN.md)

Deterministic support triage MVP for self-hosted Dify. It classifies a support question, retrieves grounded evidence from official documentation, then answers, asks for one clarification, or creates a ticket.

[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](./requirements.txt)
[![FastAPI](https://img.shields.io/badge/api-FastAPI-009688?logo=fastapi&logoColor=white)](./app/api/main.py)
[![Support%20Flow](https://img.shields.io/badge/support%20flow-deterministic-1F6FEB)](./app/support/service.py)
[![Tests](https://img.shields.io/badge/tests-pytest-6DB33F)](./tests/)
[![Replay%20Eval](https://img.shields.io/badge/eval-replay-F59E0B)](./scripts/run_eval.py)
[![Architecture](https://img.shields.io/badge/docs-architecture-6B7280)](./docs/ARCHITECTURE.md)

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts\fetch_sources.py
.\.venv\Scripts\python scripts\build_index.py
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/readyz'
```

`/readyz` is the support-answering readiness check. If it returns `503`, the local corpus or chunk index is not ready yet.

## What This Repo Does

This repository turns a bounded Dify support workflow into a runnable backend service. It does not try to be a general chatbot. It takes one support question, classifies it into a fixed set of categories, retrieves evidence from official Dify docs, and returns one of three outcomes:

- `answered`
- `needs_clarification`
- `ticket_created`

The scope is intentionally narrow:

- one product corpus: Dify official English docs
- one request path: classify -> retrieve -> decide
- one clarification turn at most
- one local persistence layer for runs, retrieval hits, tickets, and snapshot metadata

## What Is Implemented

- deterministic support triage for `deployment`, `configuration`, `knowledge-base`, `integration`, and `unclassified`
- fixed-slot extraction for `deployment_method`, `version`, `error_message`, and `environment`
- manifest-guided local retrieval over ingested Dify documentation
- synchronous support outcomes through `POST /v1/support/ask`
- support follow-up handling through `follow_up_run_id`
- local ingestion, snapshot persistence, and snapshot drift rejection within the same `snapshot_version`
- replay evaluation for support cases and threshold checks
- readiness and liveness separation through `GET /readyz` and `GET /healthz`

## Why It Is Designed This Way

- Deterministic first: the current baseline stays runnable without model credentials and keeps decision behavior inspectable.
- Single corpus: support answers stay grounded in official Dify documentation instead of mixed web sources.
- Explicit escalation: vague or low-evidence questions should fail into clarification or ticketing, not forced answers.
- Local evidence trail: runs, retrieval hits, tickets, and replay artifacts make the current behavior auditable.

## Engineering Evidence

The current claims are backed by code and runnable entry points in the repository:

- API entry and health endpoints: [`app/api/main.py`](./app/api/main.py)
- support decision flow: [`app/support/service.py`](./app/support/service.py)
- local retrieval and indexing entry: [`app/retrieval/index.py`](./app/retrieval/index.py)
- ingestion and snapshot handling: [`app/ingest/`](./app/ingest/)
- SQLite schema and persistence helpers: [`scripts/init_db.sql`](./scripts/init_db.sql), [`app/models/db.py`](./app/models/db.py)
- integration and unit coverage: [`tests/`](./tests/)
- replay evaluation runner: [`scripts/run_eval.py`](./scripts/run_eval.py)
- container packaging entry: [`Dockerfile`](./Dockerfile), [`docker-compose.yml`](./docker-compose.yml)

## Boundaries / Non-goals

This project is:

- an AI application prototype
- a Python backend service
- a bounded support baseline for self-hosted Dify operations

This project is not:

- a remote-LLM support service
- a multiple-agent runtime
- a frontend or dashboard product
- an async worker or queue-based system
- an embedding-based retrieval stack
- a production deployment target

Deliberate omissions:

- no external model provider integration
- no broad multi-source knowledge corpus
- no memory layer or long-running conversation state
- no infrastructure abstraction for multiple retrieval backends

## Further Reading

- architecture notes: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- demo script: [`docs/DEMO_SCRIPT.md`](./docs/DEMO_SCRIPT.md)
- interview notes: [`docs/INTERVIEW_NOTES.md`](./docs/INTERVIEW_NOTES.md)
- resume-safe project bullets: [`docs/RESUME_BULLETS.md`](./docs/RESUME_BULLETS.md)
- current implementation details and frozen scope record: [`SPEC.md`](./SPEC.md)
