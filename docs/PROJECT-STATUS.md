# Brain project status

Last verified: 2026-09-21.

## Purpose

Brain is an auditable shared-experience system for AI agents. Agents are its primary consumers; the web application is the review and operations surface. Personal long-term memory and external literature evidence remain separate systems and must not be treated as Brain knowledge.

Two supported flows:

- Local experience: retrieve → selectively apply → verify the real task → record an outcome → submit evidence-backed proposals → curate/export.
- External evidence: retrieve an approved source excerpt → verify that it supports the claim → cite the real source. External retrieval never creates Brain knowledge or outcomes automatically.

## Release state

The backend-convergence implementation is complete and deployed in the operator environment. This repository contains the portable implementation, strict contracts, client skill, tests, and operator-neutral documentation.

Implemented and verified:

- strict versioned execution-event, proposal, source-reference, and knowledge-revision contracts;
- durable SQLite outbox with retry leases, exact acknowledgement, and authenticated reconciliation of ambiguous upload outcomes;
- server-owned principal mapping with actor/workspace/project isolation;
- sanitized hook capture without replaying original side effects;
- restartable extraction, exact-version checks, immutable revisions, ancestry, conflict isolation, and authorized dispositions;
- authenticated directives, separated directive/formal/candidate retrieval, and verified-use accounting;
- gated archive retrieval that requires an empty ordinary search plus an explicit scoped request;
- reference-only notification events that cannot perform knowledge transitions;
- schema=1 compatibility, disposable V2 end-to-end coverage, and rollback by disabling V2 while preserving data;
- portable `skills/brain-loop` client package and multi-agent adapter.

Deployment-specific tokens, host aliases, absolute paths, backup destinations, dataset identifiers, local databases, generated evaluation data, and private operational snapshots are intentionally excluded from version control.

## Deliberate open policy items

These are not implementation gaps:

1. Automatic promotion and inactivity-archive thresholds remain disabled until real usage data supports explicit numeric values.
2. A paired Brain-on/off effectiveness pilot has not been run. Tests prove contracts and operability, not a measured improvement in task success.
3. UI redesign and literature-library expansion are separate workstreams.

## Verification boundary

The release test suite covers contracts, authorization, compatibility, recovery, governance transitions, and disposable end-to-end behavior. Production deployment additionally requires:

- an operator-approved principal mapping;
- a tested independent backup and restore path;
- secure token storage outside the repository;
- explicit policy values before automatic promotion/archive is enabled;
- deployment-specific smoke tests after restart.

See:

- `docs/agent-install.md` — client installation and verification
- `docs/backend-convergence-operations.md` — rollout and rollback gates
- `docs/brain-effectiveness-evaluation.md` — paired effectiveness evaluation design
- `docs/dify-knowledge-addon.md` — optional external evidence boundary
- `docs/knowledge-governance-decisions.md` — governance authority model
- `docs/knowledge-lifecycle-decisions.md` — lifecycle policy
