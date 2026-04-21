PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS support_runs (
    run_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    request_payload TEXT NOT NULL,
    status TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS retrieval_hits (
    hit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT,
    snippet TEXT NOT NULL,
    score REAL,
    snapshot_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES support_runs (run_id)
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    resolution_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES support_runs (run_id)
);

CREATE TABLE IF NOT EXISTS document_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    snapshot_version TEXT NOT NULL,
    title TEXT,
    stored_path TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_support_runs_created_at
    ON support_runs (created_at);

CREATE INDEX IF NOT EXISTS idx_retrieval_hits_run_id
    ON retrieval_hits (run_id);

CREATE INDEX IF NOT EXISTS idx_tickets_run_id
    ON tickets (run_id);

CREATE INDEX IF NOT EXISTS idx_document_snapshots_source_version
    ON document_snapshots (source_url, snapshot_version);
