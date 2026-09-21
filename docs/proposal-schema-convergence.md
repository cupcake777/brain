# Proposal schema convergence — design draft

Status: proposed contract, not implemented or deployed. Scope: proposal input only; no production DB migration, endpoint replacement or policy change authorized by this document.

## Minimal authoring contract

```json
{
  "schema": 2,
  "content": "A self-contained reusable lesson, including when it applies and necessary exceptions.",
  "evidence": [
    {"ref": "sanitized source locator", "excerpt": "actual supporting observation or verification"}
  ],
  "scope": "global"
}
```

Required authored fields: content and evidence. schema is the protocol discriminator, not knowledge content. scope is optional and defaults to global; it expresses applicability, not authorization. Context or exceptions necessary to avoid misuse belong in content. Do not add conditional/rationale/verification fields until a concrete consumer requires them.

Evidence: nonempty array of strict objects, each with nonempty ref and excerpt. A source locator is not proof by itself; excerpts must support the lesson. Do not fetch arbitrary refs automatically. No credentials, personal facts or infrastructure disclosure. Evidence validation is structural; adequacy is still a review decision.

## Removed from mandatory authoring

- summary: derive a display label, preserving full content as truth.
- observation and why_it_matters: keep useful rationale in content or evidence only, not compulsory repeated prose.
- suggested_memory: becomes content, the canonical lesson text.
- category and domain: enrichment/routing metadata; not required from authors. Derived classifications may be corrected during review and are not evidence.
- project vs scope: one input scope; internal compatibility adapters may still retain project_key. Scope meanings must be documented before adopting structured scoping.
- risk_level: cannot be trusted as author-declared safety clearance; assess by server/reviewer, preserving existing safeguards.
- agent/host_hash: separate transport provenance, client supplied and unverified unless bound to identity; never conflate with evidence.

Server-owned: proposal_id, created_at, workflow status, source identity/provenance, derived title/classification and governance assessment. Do not accept author-supplied approval/stage/confidence.

## Compatibility principles

Do not silently reinterpret existing schema=1 or overwrite legacy records. Implement a version-discriminated input normalizer only after contract review. Existing schema=1 clients remain supported during transition. Map schema=2 content to the existing canonical memory text without generating invented observations or evidence. Legacy presentation/storage can remain until downstream review/export consumers have been audited. No DB migration solely to make the input shorter.

## Before implementation

1. Review representative real proposals to check whether scope/content/evidence preserve all necessary information; sanitize examples and do not rewrite production.
2. Decide version signaling and provenance envelope together with portable client. No changes to retrieval/Dify schemas.
3. Audit ProposalWriter, ingestion, dedup, review detail, integration and exporters for mandatory six-section assumptions.
4. Add strict-input tests: missing/blank/wrong types/unknown fields, malformed evidence, sensitive text rejection, no writes on rejection; legacy schema=1 regression.
5. Add end-to-end disposable inbox/DB tests to prove content and evidence survive queue/review/integration/export without fabricated fields.
6. Update template/client/docs; run full tests. Deploy/restart only after approval, preserving existing dirty worktree changes.

This design makes authoring concise; it does not remove traceability, safety gates or review requirements.
