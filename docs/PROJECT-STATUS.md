# Brain project status

Last verified: 2026-11-28.

## Purpose

Brain is an auditable shared-experience system for AI agents. Agents are its primary consumers; the web application is the review and operations surface. Personal long-term memory and external literature evidence remain separate systems and must not be treated as Brain knowledge.

Two supported flows:

- Local experience: retrieve → selectively apply → verify the real task → record an outcome → submit evidence-backed proposals → curate/export.
- External evidence: retrieve an approved source excerpt → verify that it supports the claim → cite the real source. External retrieval never creates Brain knowledge or outcomes automatically.

## Operator workspace

The default web entry is a Chinese experience workspace with one shared navigation and appearance across overview, knowledge, review, project activity, server/directory inventory, chart templates, and settings. Chart details, saved preferences, password feedback, and advanced history/editor views use the same workspace shell. Readable detail pages separate Chinese reading guides, attributed editorial recommendations, original submissions, evidence, and decision controls. Advanced relationship/history views and export actions remain reachable from the relevant detail or processing-history link.

`editorial_reviews` stores append-only, session-attributed notes with a digest of the reviewed content and environment scope. Editing either invalidates the visible recommendation; recording a note rejects stale or missing targets within a write transaction. These notes do not change proposal approvals or knowledge stages. A submitter is never displayed as a reviewer without an explicit review record. The November 27 operator snapshot read all 106 then-pending compatibility proposals and prepared 98 Chinese knowledge guides; its evidence scope is submitted text, not re-execution or independent verification of original remote material. New unreviewed content remains explicitly unreviewed; this release does not introduce an automatic semantic reviewer.

The review inbox opens by topic, with an optional flat list. Topic membership is a navigation aid, not a claim of equivalence. `editorial_topics`, `editorial_topic_members`, and `editorial_relationships` retain attributed comparisons and evidence separately from the original records. Directed merge suggestions and refinements, symmetric conflicts, and background links are visible at both endpoints, including proposal-to-knowledge links. Both content and applicability digests must still match; a change at either endpoint withholds the old relationship pending another comparison. No relationship approves, rejects, merges, or exports records. The November 27 operator snapshot indexes 106 then-pending proposals and 98 active knowledge records into 15 topics, with 40 proposal-to-proposal and 32 proposal-to-knowledge comparisons.

The server/directory inventory separates submission origin from applicability and links compatibility proposals to their readable review pages. The chart browser reads the configured local catalog, renders an explicit empty state when it has no entries, and preserves catalog-bound asset/source validation. Display preferences persist through the existing settings API; browser-password changes return to the workspace, retain the authenticated session, and preserve agent access tokens. Token-only deployments manage tokens through service configuration rather than the browser-password form.

## Knowledge detail exploration (November 28, 2026)

Readable knowledge details include a direct neighborhood graph and an evolution timeline. The graph combines current digest-validated editorial comparisons with explicitly stored lineage and conflict relationships, preserving direction and provenance. Topic membership alone creates no edge. Selecting a node or relationship opens its scope, source, evidence and record link; conflict, refinement, merge recommendation, lineage and background filters are available. Desktop and mobile use different fixed layouts, with progressive disclosure, keyboard selection and the workspace theme.

The timeline combines recorded lifecycle timestamps, processing decisions, current and historical editorial reviews, proposal links, exact candidate exposures and caller feedback. Events sort by parsed timestamps, expose evidence and traffic classification, and support category filters, chronological reversal and incremental display. Historical notes remain historical; recorded processing decisions do not imply that old content snapshots exist. Candidate retrieval, adoption, task result and user validation retain separate meanings. Large histories explicitly show a bounded recent window per event source. Reading the view does not record retrievals or alter governance state.

Browser fixtures cover desktop/mobile, dark mode, keyboard operation, graph and history filters, evidence links, ordering, empty states, content injection and a JavaScript-disabled fallback. The standard test fixtures isolate the web background scanner because concurrent implicit and explicit proposal ingestion otherwise races in UI tests; production runtime behavior is unchanged.

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
- portable `skills/brain-loop` 1.4.2 client package and multi-agent adapter;
- separate server/home/project provenance and applicability, contextual retrieval/exports and an owner inventory;
- classified traffic, real session/task attribution, persisted verification notes and owner metrics;
- shared lexical coverage filtering with all 31 labelled regression checks passing.

Deployment-specific tokens, host aliases, absolute paths, backup destinations, dataset identifiers, local databases, generated evaluation data, and private operational snapshots are intentionally excluded from version control.

## Deliberate open policy items

These are not implementation gaps:

1. Automatic promotion and inactivity-archive thresholds remain disabled until real usage data supports explicit numeric values.
2. A 12-task historical replay pilot has run (24 model calls): acceptance off 10/12, on 12/12, with higher token usage. This is not live-user success or statistical proof; see the recorded limitations in `brain-effectiveness-evaluation.md`.
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


## Independent proposal curation (November 28, 2026)

The operator can delegate compatibility-proposal review to independent agents and apply their explicit decisions using `scripts/curate_brain_proposals.py`. `prepare` produces an incomplete plan with content/applicability digests; agents must supply concrete decisions, evidence assessments and exact retained targets. `check` verifies the entire batch; `apply` commits the same reviewed plan atomically and records its identity, reviewer, real session, plan digest and result. Replaying an identical plan is idempotent; changed content, applicability or comparison targets invalidate it. Submission and review remain separate. No automatic semantic acceptance daemon is introduced.

The November 28 backlog review covers 107 pending submissions: 23 retained directly, 55 retained after narrowing, 24 merged into exact retained representatives, and five archived with reasons. Original proposal text and evidence remain available. New knowledge starts at `refined`, with submitted evidence and explicit scope; this does not assert historical task re-execution or independent scientific validation. Unresolved user/host applicability stays withheld from general retrieval. Reviewed comparisons can link the resulting knowledge records; topic membership remains navigation only.

`approved_db_only` knowledge remains available to scope-eligible database retrieval. Linked knowledge enters agent exports only when at least one current, scope-eligible, non-retired source proposal is `approved_for_export`. The knowledge and lane exports enforce that authorization even after materialization; withdrawal rewrites stale lane files. New materialization and merge paths retain submitted evidence without inventing verification metadata. Already linked knowledge is not silently rewritten by every worker cycle.

The environment organizer accepts an explicit `--retire-manifest`; its default retirement list is empty. The feedback pilot accepts explicit provider/configuration/credential inputs and external labelled fixtures, and labels its bundled cases as a historical deployment sample.


The applied November 28 batch leaves zero pending compatibility proposals, with 143 database-only, 392 export-approved, 36 superseded and 12 rejected/archived records. Independent comparison added 20 exact-content-bound knowledge relationships, withdrew six misleading comparisons and archived 28 comparisons invalidated by scope changes. There are 234 current typed relationships and zero stale current comparisons. These are the deployment snapshot counts, not timeless product guarantees. All 583 original proposal bodies/evidence and the 117 pre-existing knowledge records passed preservation checks.

Validation: full regression `785 passed, 5 skipped`; the subsequent relationship-withdrawal and curation regression `21 passed`. Production service/worker restart, database integrity, approved-proposal processing coverage and deployed desktop/mobile pages are checked separately. Operational plans, database backups and browser authentication stay outside the source repository.
