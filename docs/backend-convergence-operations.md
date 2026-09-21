# Brain backend convergence operations

This document covers the staged event-to-knowledge backend. The existing schema=1 API and Dify source lane remain the compatibility surface.

## Safety defaults

- `BRAIN_V2_ENABLED` defaults to false. With the flag unset, `/api/v2/brain/*` is not registered.
- If enabled without all three server-owned principal values, V2 routes fail closed with `503 principal unavailable`.
- Request headers and bodies cannot select actor, workspace, project, origin, classification, workflow state, or human authority.
- Automatic formal promotion and inactivity archive remain disabled until explicit numeric policy values are configured.
- No source URL is fetched automatically.

Required staged configuration:

```text
BRAIN_V2_ENABLED=true
BRAIN_V2_ACTOR=<server-mapped actor>
BRAIN_V2_WORKSPACE=<server-mapped workspace>
BRAIN_V2_PROJECT=<server-mapped project>
```

A static mapping is suitable only for a single trusted deployment scope. Multi-user deployment requires a reviewed session/token-to-principal adapter; do not reuse caller-controlled headers.

## Pre-rollout gates

1. Create a consistent backup of the production SQLite database and independently verify it can be restored.
2. Run migration and API tests against a disposable copy first.
3. Verify the configured principal maps to the intended workspace/project.
4. Run the full test suite and `git diff --check`.
5. Keep promotion/archive thresholds unset unless separately approved.
6. Review notification endpoint/token configuration; notifications contain references only and do not grant decision authority.

## Disposable rehearsal

Use a copied database in a temporary directory. The production database path is operator-configured; never run rehearsal writes against it. Construct `HermesRepository` first, then `EventStore` on the same copy. Verify:

- schema=1 rows remain unchanged;
- repeated V2 initialization is idempotent;
- event create/read returns exact ID, version, and digest;
- cross-project references are rejected;
- unknown upload outcomes remain held until authenticated exact ID/version/digest reconciliation;
- checked candidate acceptance binds the current knowledge revision and current source versions.

## Operator-owned adapters

The repository intentionally omits deployment-local service drop-ins, token maps, dataset UUID maps, host aliases, private backup scripts, and generated production reports. Configure those outside version control. The portable multi-agent adapter defaults to loopback and requires explicit `BRAIN_URL`, scoped token storage, and outbox paths for remote deployments.

## Rollout

1. Install the reviewed code without changing the feature flag.
2. Restart Brain and verify schema=1 health/retrieve/export paths.
3. Enable V2 with the complete principal mapping.
4. Restart Brain.
5. Verify unauthenticated V2 requests return `401`; authenticated health-compatible reads use only the configured scope.
6. Submit a sanitized probe event only if an explicit production probe is authorized. Mark probes/evaluations so they receive no promotion credit.

## Rollback

Unset `BRAIN_V2_ENABLED` and restart the service. This removes V2 routes and workers while preserving queued uploads, immutable events, proposal revisions, knowledge revisions, checks, conflicts, directives, and notification references. Do not delete V2 tables or queues as a rollback mechanism.

## Backup limitations

The portable outbox protects against process restart and ambiguous responses, not machine loss. Its SQLite snapshot must be copied to an approved independent destination before machine-loss resilience can be claimed. Windows owner-only permissions require platform-specific ACL handling.

## Hook coverage

The portable adapter registers `post_tool_call`. It records targeted tool context only and does not claim complete coverage of all agent operations. Missing hook coverage requires an explicit wrapper. Recovery uploads facts and never replays original side effects.

## Notification semantics

`ReferenceEvents` persists reference-only events. `ANotifyReferenceSender` uses `curl` (not Python urllib, which Cloudflare may block), requires an explicit HTTP(S) endpoint, and treats a response as delivered only when the response body reports a positive integer `delivered`. Delivery does not resolve a conflict or perform a lifecycle transition; an authenticated Brain decision is still required.
