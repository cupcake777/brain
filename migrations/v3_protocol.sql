-- Brain Protocol v3 Migration
-- Run via HermesRepository._init_db()

-- 1. Observations (immutable evidence)
CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    source_span TEXT NOT NULL DEFAULT '',
    quoted_excerpt TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL DEFAULT '',
    proposal_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_obs_proposal ON observations(proposal_id);
CREATE INDEX IF NOT EXISTS idx_obs_hash ON observations(content_hash);

-- 2. Memory edges (lineage)
CREATE TABLE IF NOT EXISTS memory_edges (
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    evidence_id TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (from_id, to_id, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_me_from ON memory_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_me_to ON memory_edges(to_id);
CREATE INDEX IF NOT EXISTS idx_me_type ON memory_edges(edge_type);

-- 3. Retrieval log (structured)
CREATE TABLE IF NOT EXISTS retrieval_log (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    retrieval_mode TEXT NOT NULL DEFAULT 'fts5',
    candidate_ids TEXT NOT NULL DEFAULT '[]',
    selected_ids TEXT NOT NULL DEFAULT '[]',
    used_ids TEXT NOT NULL DEFAULT '[]',
    agent TEXT NOT NULL DEFAULT '',
    session_id TEXT NOT NULL DEFAULT '',
    task_context TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rl_agent ON retrieval_log(agent);
CREATE INDEX IF NOT EXISTS idx_rl_session ON retrieval_log(session_id);
CREATE INDEX IF NOT EXISTS idx_rl_created ON retrieval_log(created_at);

-- 4. Outcome log (per-memory feedback)
CREATE TABLE IF NOT EXISTS outcome_log (
    id TEXT PRIMARY KEY,
    retrieval_log_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    helpfulness TEXT NOT NULL DEFAULT 'unknown',
    user_validated INTEGER,
    task_success TEXT NOT NULL DEFAULT 'unknown',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ol_retrieval ON outcome_log(retrieval_log_id);
CREATE INDEX IF NOT EXISTS idx_ol_memory ON outcome_log(memory_id);
CREATE INDEX IF NOT EXISTS idx_ol_helpfulness ON outcome_log(helpfulness);
