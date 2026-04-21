# Resume Bullets

## Safe Resume Bullets

- Built a FastAPI-based internal support copilot for self-hosted Dify operations, with a deterministic triage chain that classifies requests, retrieves grounded evidence from official docs, asks one clarification when needed, and escalates unresolved cases into persisted tickets.
- Implemented a local Dify documentation ingestion pipeline that fetches official English docs, stores raw and cleaned snapshots, records snapshot metadata in SQLite, and rejects silent content drift within the same snapshot batch.
- Designed deterministic chunking and local retrieval over the cleaned corpus using SQLite-backed indexing, enabling reproducible support lookups without external model or vector database dependencies.
- Added replay evaluation for support behavior using version-controlled cases, with metrics for status accuracy, citation hit rate, clarification slot matching, and escalation-path correctness.
- Hardened support decision rules for vague complaint-style knowledge-base and integration issues, reducing false answered cases and improving clarification and escalation behavior under replay evaluation.
- Kept the system locally runnable and testable with PowerShell-friendly scripts, integration tests, and minimal infrastructure assumptions.

## Words You Can Safely Use

- deterministic baseline
- support triage
- retrieval-backed
- grounded citations
- replay evaluation
- local retrieval
- SQLite-backed persistence
- bounded corpus
- snapshot drift protection
- rule-based clarification
- escalation workflow

## Words You Should Not Hard-Claim

- production-grade support platform
- autonomous agent system
- multi-agent orchestration
- semantic search platform
- LLM-powered support generation
- enterprise knowledge platform
- full document version management
- immutable snapshot history
- human-level troubleshooting
- complete RAG system
