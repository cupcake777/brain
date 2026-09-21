# Brain effectiveness evaluation

## What existing verification proves

Unit/integration tests prove implementation contracts, not task improvement. Installation/HTTP success prove reachability, not correct selection/application. Existing threshold_eval_suggested.json evaluates dedup/related pair thresholds; all 81 labels are auto_suggested, not independent ground truth. Never use it as evidence of user task gains.

Read-only baseline observed: 45 knowledge_retrieval_events, 11 retrieval_log rows, 2 outcome_log rows; helpfulness helpful=1/neutral=1, task_success unknown and user_validated null. health retrievals=297 equals sum(knowledge_nodes.retrieval_count), not request count. health outcomes=1 equals node outcome_count sum, not two raw outcome rows. Recent two portable-agent requests correspond to deployment checks, not organic consumption. Current active knowledge: canonized=380, deprecated=83. These are a point-in-time inventory, not performance claims.

## Start with a small paired pilot

Use 12 sanitized, executable past tasks: four known-rule helpful cases, four applicability traps (wrong host/project, stale rule, changed condition), four no-useful-knowledge cases. Separately use a source-evidence suite for Dify: supported passages, unrelated top-k, absent bibliography, injected instructions, malformed response, cloud unavailable. Do not collapse evidence quality and local knowledge usefulness into one score.

Freeze task inputs, Brain snapshot, model/version, tool permissions, resource budget and expected verification before runs. Hide original solutions and future evidence. Use disposable local fixtures or explicitly approved sandboxes, never live destructive VPS operations. Exclude cases where solutions already leak via skills/memory/system context, or disclose that overlap. Baseline and Brain arms must share the same non-Brain memory/skills/tools.

A: Brain off. B: Brain local experience retrieval available through the skill, otherwise same setup. Run in isolated contexts; no cross-arm memory or proposal ingestion. Randomize run order. Save prompts, relevant retrieval IDs, returned candidates, tool trace, final outputs, elapsed time and actual available token/cost measurements. Judge outputs against executable assertions blind to arm. Pilot findings are diagnostic, not statistical proof; repeat variable cases and expand held-out tasks before generalizing.

Primary: task acceptance pass, critical error/unsafe action, unsupported claim. Secondary: correct applicability, irrelevant-rule rejection, retries, duration, measured tokens/cost, feedback completeness. Applied is self-report, not primary success evidence. Improvement must be backed by a concrete action changed plus better verification, not merely a citation.

## Local retrieval-only checks

Independently label query relevance/applicability against frozen knowledge before seeing ranked scores. Evaluate Recall@5 for cases with known relevant nodes, Precision@5 where relevance is defined, and inappropriate-result acceptance/abstention on no-answer cases. Evaluate natural Chinese, English and keyword variants. Distinguish absent library coverage from failed recall and agent misuse. Use a database copy and mock/test credentials; do not add evaluation events to production metrics.

## Governance checks

In a disposable database test duplicate proposals, contradicted claims, weak evidence, private data and scoped rules. Check resulting decisions and exports, not just accepted HTTP status. Test export loading into an agent context separately. Never ingest paired-run lessons back into the frozen benchmark.

## Failure attribution and optimization

No supporting knowledge => curate evidence/coverage, not score tuning.
Supporting knowledge exists but not retrieved => improve query/index/ranking, independently evaluated.
Retrieved but not selected => improve skill triggers/tool access.
Selected outside scope/stale => improve applicability and abstention.
Correctly used but no task gain => shorten/no-op retrieval or remove irrelevant instructions.
Verified useful but no feedback => fix closure integration, not fake outcomes.

Change one factor at a time, rerun the same frozen benchmark plus held-out cases. Keep baseline artifacts and do not tune to the final test set. Live shadow usage can follow a pilot: explicitly distinguish organic tasks, audits, probes and evaluation traffic; record denominators and actual verification evidence. Do not build a success-rate dashboard until its data exists.

## Current status

This file defines evaluation only; no paired experiment has been executed, no success lift measured, no model or production routing changed. First intervention should be a small paired task pilot, not UI expansion, more auto-promotion, or unverified threshold changes.
