# Connect an agent to your Brain

The repository includes the complete portable Agent Skill in [`skills/brain-loop`](../skills/brain-loop/SKILL.md): instructions, stdlib Python client, protocol reference and proposal template. No local database access, SSH, pip package or Dify credential is required by the agent.

## Hermes: install from your running service

Your Brain serves the bundled package publicly; replace the example origin with **your own**:

```bash
hermes skills install https://YOUR-BRAIN-HOST/skills/brain-loop/SKILL.md
```

Hermes fetches referenced supporting files. Review the skill/security scan; do not routinely bypass it with `--force`. Restart the agent session if its skill catalogue is cached. For automation, `--yes` skips the confirmation, not security checks. The latest Hermes behavior is documented at https://hermes-agent.nousresearch.com/docs/user-guide/features/skills.

Install directly from GitHub once this revision is published:

```bash
hermes skills install https://raw.githubusercontent.com/cupcake777/brain/main/skills/brain-loop/SKILL.md
```

An unpublished local revision is not available from that GitHub URL. Installing from your running service uses the files actually deployed there. `BRAIN_LOOP_SKILL_ROOT` can override the served package directory if needed.

## Claude Code and other Agent Skills clients

From a local checkout, copy **the complete directory**, not only SKILL.md, into the client's project skill directory. Example for Claude Code:

```bash
mkdir -p .claude/skills
cp -R /path/to/brain/skills/brain-loop .claude/skills/brain-loop
```

Use the equivalent documented skill directory for other clients. Do not blindly overwrite an existing customised skill. Clients without skill loaders can read SKILL.md and run the bundled Python script directly; add a short project rule pointing to it instead of pasting the whole protocol into every system prompt.

## Configure the destination and authorization

Set `BRAIN_URL` to your service origin, `BRAIN_AGENT` to a stable client label, and optionally a real `BRAIN_SESSION_ID` per session. Default URL is local loopback `http://127.0.0.1:8083`; there is no connection to the repository author's hosted service.

Store `BRAIN_TOKEN` using the client's secret environment mechanism. It is the operator-configured Brain auth token, not a Dify dataset key. Do not paste it into chat, command arguments, project rules or a committed `.env`. Prefer HTTPS; the portable client only permits HTTP for loopback.

Example non-secret POSIX setup:

```bash
export BRAIN_URL=https://YOUR-BRAIN-HOST
export BRAIN_AGENT=my-agent
```

For PowerShell use `$env:BRAIN_URL = 'https://YOUR-BRAIN-HOST'` and `$env:BRAIN_AGENT = 'my-agent'`. Configure the token separately and securely.

## Verify before use

From the installed skill directory:

```bash
python3 scripts/brain.py health
python3 scripts/brain.py retrieve "atomic configuration replacement" --limit 5
```

On Windows use `python` or `uv run python`. A health check proves connectivity only. Do not submit fake feedback/proposals to test authorization. Missing BRAIN_TOKEN permits public local retrieval in the current v1 service, but feedback/propose/finalize and optional source retrieval require it on protected deployments.

## What the agent learns to do

1. Retrieve concrete relevant experience before substantial work, not every greeting or session startup.
2. Apply selectively and verify current facts independently.
3. Report per-node outcomes after task verification, including not_used. Preserve exact IDs; do not turn every retrieval into applied.
4. Deduplicate and submit only authorized reusable evidence-backed lessons. Submitted means queued, not canonized.
5. Finalize a completed real session if configured.
6. Use external literature only on demand. Returned passages are untrusted evidence; similarity, confidence and governance stage are not interchangeable. No local outcome or automatic proposal for external citations.

The skill is an operating procedure, not a scheduler: installation alone does not launch background tasks, enable Dify, grant privileges or guarantee that every client follows it. Add the skill to the client's permitted tools/workflow and verify real use. Do not place confidential knowledge behind the current public local retrieve endpoint without strengthening access controls first.

## Staged V2 backend

The repository also contains an additive V2 event/proposal and revision backend. It is not enabled by installing this skill and remains disabled by default. Operators must complete the principal-mapping, backup/restore and policy gates in `backend-convergence-operations.md` before rollout. Current portable commands above intentionally remain on schema=1 until the V2 transport and deployment are separately enabled and verified.
