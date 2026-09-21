# Brain knowledge scope, consumption and revision decisions

Status: user-approved design direction, not implemented/deployed. Supplements knowledge-governance-decisions.md. Current live API and records remain unchanged.

## Scope

Project experience remains within its project. Do not automatically broaden scope during extraction, merging, promotion or archive recovery. Generic rules and explicit cross-project user directives have separate authorized scope. Cross-project promotion, if later requested, is a distinct change requiring review/checks.

## Consumption

Return separate lanes for explicit rules, formal experience and candidate references. Candidates are visibly unverified, limited, selectively used and cannot override directives or authorize operations. Retrieval traffic alone does not promote knowledge.

Archive access requires BOTH: normal authorized retrieval found no usable knowledge, AND the agent explicitly requests archive search. No automatic archive fallback on an empty response. Scope/authorization still apply. Mark archived results and require renewed validation before reactivation; retrieving an archived item does not reactivate it.

## Per-knowledge version graph

Each knowledge item has a stable identity and immutable revisions. Preserve parent revisions, originating events/proposals, evidence and exact-version check results. Present a future human-facing log/graph of evolution: creation, revision, evidence addition, conflict, replacement, split/merge and archive/reactivation. This is git-like semantics, not a decision to create a physical Git repository per item or implement UI now.

Keep knowledge revision edges separate from topical/semantic knowledge graph edges. Splits/merges may connect multiple knowledge identities; do not treat a similarity edge as revision ancestry. Author/proposer identity and timestamp must retain provenance accuracy.

Validation reuse: evidence additions retain historical support for unchanged claims; claim or applicability changes invalidate affected current-version gates. Old evidence/checks remain attached to old revisions, never silently rebound. A changed version cannot merge based on old all-green checks. Recheck evidence additions for sensitivity and structural validity as applicable.

## Engineering details still to specify

Strict object types, revision concurrency, graph edge enums, exact promotion thresholds, source retention and required check policy. No new schema fields or production migrations are implied by this approval.
