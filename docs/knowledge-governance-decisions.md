# Brain knowledge governance — agreed direction

Status: user-approved design direction; not implemented or deployed. This document supersedes conflicting suggestions in proposal-schema-convergence.md; existing live schema=1 remains unchanged. Exact strict event/proposal types and check thresholds are not yet finalized.

## Ingestion and derivation

Capture actual events via hooks where possible without extra main-model calls. Preserve raw events immutably with provenance and verification records; minimize/redact before sharing, do not upload all transcripts. Brain Hub may derive multiple candidate knowledge items from one event, retaining source links. Extraction does not itself establish truth.

## Two authority lanes

1. Explicit user directives: apply immediately within that user's authorized scope, without retrieval-count or trial-use promotion. If synchronizing is delayed, the agent must still honor the current instruction. Do not autoarchive solely for inactivity. New explicit instruction updates the prior directive with history; suspected conflicts are surfaced, not silently resolved by an LLM. Overrides of other users or higher-priority authorization are not granted.
2. Event-derived experience: enter candidate pool, receive clearly labeled selective trial use, then qualify for formal knowledge according to required checks and verified real-task feedback. Candidate text never grants execution permission; high-risk actions cannot be justified by candidate knowledge alone.

## Updating and conflict

Same experience: update concisely with version history and additional evidence, not unlimited appended prose. Deduplicate source events. Track repeated verified mistakes/reminder priority separately from evidential confidence. Repeated retrieval or self-reported applied does not establish correctness.

Actual unresolved contradictions: preserve competing versions/evidence, suspend affected knowledge and dependent items, route a focused decision to human via anotify. Condition differences are not automatically contradictions. Explicit new user instructions are not treated as equal-authority machine inferences.

## Promotion and archive

Count independent real-task verified useful applications, not API calls, probes, retries or duplicated events. No fixed 3/month promotion threshold approved yet. Required checks bind exact proposal/knowledge version; changes invalidate affected checks. Structural checks alone do not prove semantic support.

Archive policy: experience inactivity may trigger review/archive; 90 days is a tentative signal, not an approved universal cutoff. Archive exits default retrieval but remains traceable. Explicit user directives and rare critical safeguards are exempt from automatic inactivity expiration. Dify archive transfer is optional future work, preserving provenance/access restrictions; not automatically enabled and not a truth upgrade.

## Consumption

Cross-project authorized directives/generic rules return actionable constraints; project knowledge returns digested experience with source tracing. Keep machine/environment applicability separate from user/workspace access authorization. A preference unrestricted by hardware does not become universal across users.

## Recovery and responsibilities

Client-side durable capture and idempotent/versioned upload; automatic recovery/enrichment/checks for normal flows. Temporary provider/network failures wait/retry without fake completion. Human handles unrecoverable evidence gaps, unresolved contradictions, authorization issues and persistent recovery failures. Never automatically replay original side-effectful operations.

anotify aggregates agent/task state, references, pending decisions and selected notifications. Brain owns knowledge; task system owns task truth; anotify must not become a duplicate authoritative store.

## Remaining implementation decisions

- Hook capture boundaries, redaction, durable event and source-reference format.
- Strict types, version concurrency and required-check contracts.
- Empirically informed verified-use promotion and archive policies.
- Identity/workspace authorization and integration details.

No production configuration, existing records, client schema or notification integration changed by this design approval.
