CREATE INDEX idx_embeddings_status
                    ON entity_embeddings(entity_type, status);
CREATE INDEX idx_kn_category ON knowledge_nodes(category);
CREATE INDEX idx_kn_domain ON knowledge_nodes(domain);
CREATE INDEX idx_kn_parent ON knowledge_nodes(parent_id);
CREATE INDEX idx_kn_stage ON knowledge_nodes(stage);
CREATE INDEX idx_kn_supersedes ON knowledge_nodes(supersedes);
CREATE INDEX idx_kre_created ON knowledge_retrieval_events(created_at);
CREATE INDEX idx_me_from ON memory_edges(from_id);
CREATE INDEX idx_me_to ON memory_edges(to_id);
CREATE INDEX idx_me_type ON memory_edges(edge_type);
CREATE INDEX idx_obs_hash ON observations(content_hash);
CREATE INDEX idx_obs_proposal ON observations(proposal_id);
CREATE INDEX idx_ol_helpfulness ON outcome_log(helpfulness);
CREATE INDEX idx_ol_memory ON outcome_log(memory_id);
CREATE UNIQUE INDEX idx_ol_pair ON outcome_log(retrieval_log_id, memory_id);
CREATE INDEX idx_ol_retrieval ON outcome_log(retrieval_log_id);
CREATE INDEX idx_pkl_knowledge
                    ON proposal_knowledge_links(knowledge_id);
CREATE INDEX idx_rl_agent ON retrieval_log(agent);
CREATE INDEX idx_rl_created ON retrieval_log(created_at);
CREATE INDEX idx_rl_session ON retrieval_log(session_id);
CREATE INDEX idx_tc_action ON thought_chains(action);
CREATE INDEX idx_tc_node ON thought_chains(node_id);
CREATE TABLE check_runs (
                id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                proposal_version INTEGER NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL
            );
CREATE TABLE durable_jobs (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL,
                state TEXT NOT NULL,
                enqueued_at TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL
            );
CREATE TABLE entity_embeddings (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dimension INTEGER NOT NULL DEFAULT 0,
                    vector BLOB,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (entity_type, entity_id)
                );
CREATE TABLE exports (
                    scope_type TEXT NOT NULL,
                    project_key TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    rebuilt_at TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    PRIMARY KEY (scope_type, project_key, file_name)
                );
CREATE TABLE knowledge_nodes (
                    id TEXT PRIMARY KEY,
                    parent_id TEXT,
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'fact',
                    domain TEXT NOT NULL DEFAULT 'general',
                    stage TEXT NOT NULL DEFAULT 'draft',
                    operation TEXT NOT NULL DEFAULT 'draft',
                    confidence REAL NOT NULL DEFAULT 0.3,
                    source TEXT NOT NULL,
                    evidence TEXT DEFAULT '[]',
                    supersedes TEXT,
                    merged_from TEXT DEFAULT '[]',
                    contradicts TEXT DEFAULT '[]',
                    verified_by TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    refined_at TEXT,
                    verified_at TEXT,
                    deprecated_at TEXT,
                    retrieval_count INTEGER NOT NULL DEFAULT 0,
                    last_used_at TEXT,
                    correction_count INTEGER NOT NULL DEFAULT 0
                , outcome_count INTEGER NOT NULL DEFAULT 0, last_outcome_at TEXT, kind TEXT NOT NULL DEFAULT 'fact', trigger_terms TEXT NOT NULL DEFAULT '[]', use_when TEXT NOT NULL DEFAULT '', avoid_when TEXT NOT NULL DEFAULT '', success_signal TEXT NOT NULL DEFAULT '', failure_signal TEXT NOT NULL DEFAULT '');
CREATE VIRTUAL TABLE knowledge_nodes_fts USING fts5(
                    id UNINDEXED,
                    summary,
                    content,
                    category,
                    domain
                );
CREATE TABLE 'knowledge_nodes_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;
CREATE TABLE 'knowledge_nodes_fts_content'(id INTEGER PRIMARY KEY, c0, c1, c2, c3, c4);
CREATE TABLE 'knowledge_nodes_fts_data'(id INTEGER PRIMARY KEY, block BLOB);
CREATE TABLE 'knowledge_nodes_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
CREATE TABLE 'knowledge_nodes_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
CREATE TABLE knowledge_retrieval_events (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    agent TEXT NOT NULL DEFAULT '',
                    host TEXT NOT NULL DEFAULT '',
                    node_ids TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    outcome_recorded_at TEXT
                , session_id TEXT NOT NULL DEFAULT '', host_id TEXT NOT NULL DEFAULT '', finalized_at TEXT, final_result TEXT);
CREATE TABLE memory_edges (
                    from_id TEXT NOT NULL,
                    to_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    evidence_id TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (from_id, to_id, edge_type)
                );
CREATE TABLE observations (
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
CREATE TABLE outbox_events (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                reference_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL
            );
CREATE TABLE outcome_log (
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
CREATE TABLE proposal_current (
                id TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                digest TEXT NOT NULL,
                workflow_state TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
CREATE TABLE proposal_knowledge_links (
                    proposal_id TEXT PRIMARY KEY,
                    knowledge_id TEXT NOT NULL,
                    sync_action TEXT NOT NULL DEFAULT 'created',
                    synced_at TEXT NOT NULL,
                    FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id),
                    FOREIGN KEY (knowledge_id) REFERENCES knowledge_nodes(id)
                );
CREATE TABLE proposal_revisions (
                id TEXT NOT NULL,
                version INTEGER NOT NULL,
                project_id TEXT,
                agent_id TEXT NOT NULL,
                occurred_at TEXT,
                action TEXT,
                result TEXT,
                lesson TEXT,
                draft INTEGER NOT NULL,
                source_refs TEXT NOT NULL,
                workflow_state TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL,
                received_at TEXT NOT NULL,
                PRIMARY KEY (id, version)
            );
CREATE TABLE proposals (
                    proposal_id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL,
                    source_host TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    project_key TEXT NOT NULL,
                    category TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    observation TEXT NOT NULL,
                    why_it_matters TEXT NOT NULL,
                    suggested_memory TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    state TEXT NOT NULL,
                    semantic_hash TEXT NOT NULL,
                    semantic_duplicate_of TEXT,
                    supersedes TEXT,
                    reviewer_priority REAL NOT NULL DEFAULT 1.0,
                    retrieval_count_30d INTEGER NOT NULL DEFAULT 0,
                    inserted_at TEXT NOT NULL
                , weight REAL NOT NULL DEFAULT 1.0, domain TEXT NOT NULL DEFAULT '');
CREATE TABLE retrieval_log (
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
CREATE TABLE schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
CREATE TABLE source_documents (
                id TEXT NOT NULL,
                version INTEGER NOT NULL,
                url TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                bytes_digest TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL,
                PRIMARY KEY (id, version)
            );
CREATE TABLE source_events (
                id TEXT NOT NULL,
                version INTEGER NOT NULL,
                project_id TEXT,
                agent_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                client_digest TEXT NOT NULL DEFAULT '',
                action TEXT,
                result TEXT,
                origin TEXT NOT NULL,
                classification TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                principal_actor TEXT NOT NULL,
                principal_workspace TEXT NOT NULL,
                principal_project TEXT NOT NULL,
                received_at TEXT NOT NULL,
                source_refs TEXT NOT NULL,
                PRIMARY KEY (id, version)
            );
CREATE TABLE sqlite_stat1(tbl,idx,stat);
CREATE TABLE thought_chains (
                    id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    evidence_used TEXT DEFAULT '[]',
                    decision TEXT NOT NULL,
                    confidence_in_decision REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (node_id) REFERENCES knowledge_nodes(id)
                );
