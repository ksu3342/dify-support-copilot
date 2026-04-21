# Interview Notes

## What Problem This Project Solves

This project turns internal support around self-hosted Dify into a bounded engineering workflow instead of an open-ended chatbot.

The core problem is not "can a model answer doc questions". The harder problem is:

- deciding when a question is answerable now
- deciding when more context is required
- deciding when to escalate instead of hallucinating confidence
- keeping the support corpus bounded and explainable
- measuring behavior changes with replay eval

## Why This Is Not a Generic Doc QA Demo

The repo goes beyond straight retrieval chat in several ways:

- it has explicit support outcomes, not just free-form text output
- it supports one clarification turn and then escalation
- it logs retrieval hits and persists tickets
- it treats vague complaint-style queries differently from how-to queries
- it has replayable eval cases for behavior regression detection

That makes it closer to an internal support triage assistant than a generic RAG sample.

## Key Engineering Decisions

### Deterministic baseline before LLM

Why:

- easier to run without secrets
- easier to verify
- easier to debug
- easier to evaluate with replay

Tradeoff:

- lower language flexibility
- more rule maintenance

### Single authoritative corpus

Why:

- support systems degrade quickly when sources are noisy
- official Dify docs are a defensible authority boundary
- easier to explain retrieval misses

Tradeoff:

- narrower coverage
- some real-world troubleshooting scenarios still need ticket escalation

### Snapshot drift rejection

Why:

- same `snapshot_version` silently changing content breaks reproducibility
- replay and interview claims need a stable data baseline

Tradeoff:

- stricter fetch behavior
- occasional manual batch/version updates are required

### Replay eval before more features

Why:

- false-answered behavior is more dangerous than missing a shiny feature
- behavior changes need evidence

Tradeoff:

- slower visible feature growth
- more effort spent on infra and measurement

## What I Deliberately Did Not Build

- no remote LLM integration
- no vector database platform
- no multi-agent orchestration
- no frontend
- no queue/worker architecture
- no broad multi-product knowledge system

Reason:

The bottleneck was not feature count. The bottleneck was making one support loop concrete, bounded, and measurable.

## If Asked "Why Not Use LLM First?"

Suggested answer:

I intentionally started with a deterministic baseline because it let me make the workflow verifiable before adding model variance. The key engineering problem was not model sophistication; it was proving the support chain, the escalation boundary, and the replay loop. Once that existed, adding an LLM could be an incremental replacement of classifier and answer components rather than a hand-wavy demo.

## If Asked "Why Not Use a Vector DB?"

Suggested answer:

At this scale, SQLite FTS5 was the simplest retrieval backend that kept the project easy to run, inspect, and replay locally. The product framing still treats retrieval as a lightweight local retrieval step. I chose not to introduce Chroma/FAISS/Milvus because the main value at this stage was support workflow correctness, not infrastructure breadth.

## If Asked "Why Not Multi-Agent?"

Suggested answer:

Because the problem did not need it. Multi-agent architecture would add orchestration complexity before the single support loop was trustworthy. For a bounded support triage path, deterministic stages with replay evaluation produce a much stronger engineering story than multiple agents coordinating on an unmeasured workflow.

## Strong Talking Points

- bounded scope beats inflated architecture
- escalation is a feature, not a failure
- replay eval made rule bugs visible and fixable
- authoritative corpus boundary matters more than adding more sources
- support quality depends on decision rules, not only retrieval accuracy
