# Brain UI direction (proposal, not implemented)

## Purpose

The operator reviews whether shared experience is supported, useful, contradictory or awaiting action; agents are the main retrieval clients. External libraries supply evidence, not new canon. Feel: a dense research ledger, not a marketing dashboard.

Domain: evidence, provenance, review, lifecycle, outcomes, contradictions, version history. Color world: paper/off-white, ink/graphite, muted amber, moss green, terracotta warning, blue-gray metadata. One interaction accent; colors always accompanied by text.

## Structure

Two separate views: Knowledge ledger and Literature evidence. The first preserves local stages/confidence/outcomes, the second uses source titles/current-index citation IDs and cloud response state. No mixed score ranking.

Knowledge: top compact queue (pending proposals, contradictions, stale review flags) followed by dense rows: summary/domain/stage/feedback distribution/effective sample count/last activity. Detail opens as side rail with full evidence, source, revision history and next allowed action. Avoid card walls, fake KPI hero numbers and automatic cloud calls.

Literature: explicit search, source/dataset selector only from allowlist, excerpt-first results, title/source IDs and genuine bibliographic metadata. Missing metadata visible, copying citation supported, truncation visible. Empty/unavailable/partial are distinct states. No knowledge confidence or promotion badges on excerpts. Do not show quota remaining until a real authorized backend endpoint provides it.

## Semantics

Stage and outcome are distinct labels; canonized is not interchangeable with applied. Display usefulness with denominator and missing-feedback count. Small samples display insufficient evidence; no fabricated universal n>=5 significance. Recency flags request review, not automatic invalidation. Keep thresholds operator-controlled, not introduced silently by UI.

## Typography/interaction

Readable sans-serif body, restrained optional serif section titles, tabular numerals for comparisons, monospace IDs/time. Thin dividers, no decorative shadows. Keyboard search/filter/focus states; mobile readable stacked records with accessible targets. Current user choice is advice only: no frontend deployment authorized here.

## Agent onboarding

A small Connect Agent action offers own-origin install command, setup variables and non-writing health check. Never reveal tokens in public UI, JS or screenshots. Full install guide is docs/agent-install.md and package is skills/brain-loop.
