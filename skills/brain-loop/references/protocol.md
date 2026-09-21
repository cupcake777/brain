# Brain HTTP protocol schema 1

Set BRAIN_URL to the user's service origin. Bundled client defaults to local loopback, not a hosted third-party service. Use HTTPS remotely. Use BRAIN_TOKEN securely for protected calls. There is no client-side Dify key.

## Endpoints

| Method/path | Authorization in protected v1 deployment | Purpose |
|---|---|---|
| GET /api/v1/brain/health | Public | schema/status/counters |
| POST /api/v1/brain/retrieve | Public | Local curated experience + recorded retrieval event |
| POST /api/v1/brain/outcome | Bearer/session | Feedback bound to returned local candidates |
| POST /api/v1/brain/propose | Bearer/session | Queue a proposal, not approval |
| POST /api/v1/brain/finalize | Bearer/session | Close session and pending feedback |
| POST /api/v1/brain/sources/retrieve | Always authenticated; browser CSRF | Optional external evidence |

The server's auth configuration matters. Public experience retrieval should not expose confidential knowledge. Installing a skill does not change access controls or enable Dify. Public skill assets can be served at `/skills/brain-loop/SKILL.md` with relative support files.

## Local retrieval

Request: query required <=1000 chars; limit 1–20; optional category/domain/agent/host_hash/session_id.
Response: schema=1, retrieval_id, query, results[], outcome_required. Results include full node_id, summary/content/category/domain/stage/confidence/score.

Keep IDs literal. Stage is governance state, confidence is internal knowledge assessment, score is query match; do not compare them to external similarity. This endpoint stores query and metadata, unlike external excerpt handling. Do not send private or secret query text.

## Outcome

Request: retrieval_id, node_id, status; optional note <=1000 chars. Status is applied/partially_helped/failed/contradicted/not_used. Candidate must belong to that retrieval. Feedback is idempotent for same status, conflicting updates return 409. Response includes recorded and proposal_recommended (a suggestion, not automatic learning).

The client retains compatibility switches task_success/user_validated, but the current schema=1 handler does not persist these fields. Do not compute validated task-success statistics from them. Applied means used and helped, not scientific validation. not_used is not failure or contradiction.

## Proposal

Required summary <=300, observation <=4000, why_it_matters <=2000, suggested_memory <=4000, nonempty evidence[] total <=8000 characters.
Evidence should carry source_type/source_uri/quoted_excerpt, all accurate and sanitized. Optional project/category/risk_level/scope/domain/agent/host_hash.
Categories: rule/fact/preference/workflow_hint/correction/resource. Risks: low/medium/high/critical.
Response submitted + proposal_id means queued. Lifecycle and export depend on the server policy; no guaranteed timing, stage promotion or automatic approval. Do not submit user facts to shared Brain without permission.

## Finalize

Request exactly agent/host_hash/session_id. Auth required by protected deployments. Close only real completed sessions after reporting outcomes. Server may finalize missing feedback separately; not a substitute for fabricated outcomes.

## External source retrieval

Request `{"query":"TET2","source":"dify","dataset":"literature","limit":5}`. Query <=1000, nonblank; limit strict integer 1–10; additional fields forbidden. Dataset alias must be server-whitelisted; no arbitrary URLs or IDs. This lane sends query to cloud.

Response schema=1/source/dataset/status/results/partial/error. Each valid result carries citation_id, dataset_id/document_id/segment_id, nullable title/score/source_url/doi/page, content <=4000, truncated. IDs locate current index only, not permanent bibliography. Page only from genuine metadata, never chunk sequence number.

- 200 ok: valid records; partial=true when some records rejected.
- 200 empty: valid zero-record response.
- 502 unavailable + invalid_upstream_response: malformed response or all nonempty records rejected.
- 429 unavailable + quota_exceeded: local UTC daily dispatch budget exhausted; Retry-After.
- 503 unavailable + disabled/invalid_config/quota_storage_unavailable: local issue.
- 502/504 unavailable + upstream_*: cloud HTTP/network/timeout issue.
- 400/413 invalid_input or dataset_not_allowed: invalid request.
- 401/403 auth/CSRF; outer middleware may return detail instead of source response envelope.

No local node_id/retrieval_id/outcome_required. No local outcome for citations. Server no query/excerpt persistence, no retries; configured daily dispatch counter includes failed dispatched calls. Concurrency cap is per-process, daily budget shared by workers using same quota DB.

## Client error semantics

Success outputs JSON stdout, exit 0. HTTP/network/config errors output error JSON stderr, exit 1. Validate the status and relevant content, not merely exit code. Respect rate limits; do not loop automatically. Tokens must not appear in arguments, logs or submitted evidence.
