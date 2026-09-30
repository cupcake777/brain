# Codex Brain workflow

Use Brain for curated reusable experience, not as an automatic transcript or error archive.

## Start a substantial task

Retrieve concrete relevant terms through the canonical client:

```bash
python3 "$BRAIN_LOOP_SKILL_ROOT/scripts/brain.py" retrieve "specific task and error terms" --limit 5
```

Preserve the returned `retrieval_id` and exact `node_id` values. Retrieved knowledge is advisory; verify current facts independently.

If the network is unavailable, local exported Markdown may be searched as an offline fallback, but that does not create a retrieval event and cannot receive attributable outcomes.

## Finish the task

For every returned candidate, report an honest outcome after verification:

```bash
python3 "$BRAIN_LOOP_SKILL_ROOT/scripts/brain.py" outcome \
  <retrieval_id> <node_id> applied --note "Verified result"
```

Use `not_used` when a result was irrelevant. Do not turn missing feedback into success or failure.

## Propose a reusable lesson

Only propose when all are true:

1. It is genuinely new or corrective.
2. It is portable beyond the current task.
3. It is likely to recur.
4. It has verified non-secret evidence.

Project progress, current run state, paths specific to one analysis, credentials, private data, and raw transcripts belong elsewhere, such as the project `.mem`.

Copy `templates/proposal.json` and use structured evidence:

```json
{
  "summary": "State one reusable lesson",
  "observation": "Describe the verified failure and fix",
  "why_it_matters": "Explain the recurring cost",
  "suggested_memory": "State the portable rule",
  "project": "global",
  "category": "workflow_hint",
  "risk_level": "low",
  "scope": "global",
  "evidence": [
    {
      "source_type": "file",
      "source_uri": "/literal/non-secret/source",
      "quoted_excerpt": "Exact sanitized evidence"
    }
  ]
}
```

Submit and wait for durable receipt:

```bash
bash ~/brain-sync-hpc.sh propose-file /path/to/lesson.json
```

Or call the client directly:

```bash
python3 "$BRAIN_LOOP_SKILL_ROOT/scripts/brain.py" propose /path/to/lesson.json --wait
```

## Interpret proposal states literally

- `queued`: file is queued; it is not yet in the proposal database.
- `ingested_pending`: proposal is durably stored in SQLite and awaits governance.
- `approved`: proposal was approved; inspect `proposal_state` for DB-only versus export approval.
- `linked`: approved proposal has a Knowledge node; only this state includes `knowledge_id`.
- `duplicate`: equivalent durable knowledge/proposal already exists.
- `rejected`: proposal was rejected; read the reason and do not report success.

Check later with:

```bash
python3 "$BRAIN_LOOP_SKILL_ROOT/scripts/brain.py" proposal-status <proposal_id>
```

`--wait` means wait for durable receipt (`ingested_pending` or a later state), not automatic approval, export, or canonization. Governance policy controls later transitions; elapsed time alone is not evidence.

## Close a configured session

After all known outcomes are reported:

```bash
python3 "$BRAIN_LOOP_SKILL_ROOT/scripts/brain.py" finalize --session-id "$BRAIN_SESSION_ID"
```

Finalize does not fabricate missing outcomes.
