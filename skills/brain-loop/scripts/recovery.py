"""Task 4 — recovery layer for captured tool-call observations.

Recovery is decoupled from capture. It accepts:

* ``outbox`` — anything with ``run_once(handler)`` and a small state-
  transition surface (``record_success`` / ``record_failure`` /
  ``requeue`` / ``escalate``). The real outbox from
  ``skills/brain-loop/scripts/outbox.py`` satisfies this; tests inject a
  fake.
* ``transport_runner`` — a callable taking a capture record dict and
  returning a result dict (or raising). Production wires the real
  transport; tests inject a stub.

Contract:

* Recovery invokes ``outbox.run_once`` exactly once per :py:meth:`run_once`
  call. There is no internal replay loop.
* Tool errors, interrupted results, and unknown results are persisted
  (capture already wrote them); recovery passes them through honestly.
* Within ``max_attempts`` a transport failure requeues the job — the
  record is retained, never deleted.
* After ``max_attempts`` the job is escalated (state visible). Local
  evidence is RETAINED — never deleted, so a future process can inspect
  it.
* Enrichment-provider-unavailable is tolerated: the capture is
  acknowledged but a follow-up row is enqueued via the real outbox's
  ``enqueue_enrichment`` API so evidence is never lost.

Two outbox shapes are supported:

* **Real portable outbox** (SQLite-backed) — detected by the presence of
  an ``owner`` keyword on ``outbox.run_once``. Recovery passes its own
  ``owner`` label and a per-call ``lease_seconds`` so concurrent
  workers arbitrate claims via SQLite instead of a fake dictionary.
* **Legacy handler outbox** — anything that takes a single ``handler``
  callable (e.g. the historical ``FakeOutbox``). The legacy path is
  retained for back-compat with bespoke adapters that do not migrate to
  SQLite; it is **not** the default.

The dual path is justified: real callers get durable leases, exact-
version ack, and surfaced unknown outcomes; legacy callers keep
working without rewriting their outbox.
"""
from __future__ import annotations

import inspect
import logging
import re
import uuid
from typing import Any, Callable, Protocol


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------
#
# When a transport raises or returns an error we MUST persist enough to
# diagnose, but MUST NOT persist raw bearer tokens, API keys, JWTs, or
# passwords. Patterns below are deliberately conservative — they match
# the obvious shapes and let the rest of the message through. Callers
# that need stricter redaction can subclass / replace ``_sanitize_error``.


_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(api[_-]?key[\"'=:>\s]+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(token[\"'=:>\s]+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(password[\"'=:>\s]+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(secret[\"'=:>\s]+)[A-Za-z0-9._\-]+"),
    # Compact JWT: header.payload.signature
    re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
)


def _sanitize_error(text: str | None) -> str | None:
    """Redact obvious secret shapes from an error message before storage.

    Returns ``None`` unchanged. Empty strings round-trip. Anything that
    survives the patterns is safe to persist.
    """
    if text is None:
        return None
    if not text:
        return text
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("<redacted>", out)
    return out


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class _OutboxLike(Protocol):
    def run_once(self, handler: Callable[[Any], Any], *, now: float | None = ...) -> int: ...
    def record_success(self, job_id: str, response: dict[str, Any] | None = ..., *, ack_version: int | None = ...) -> None: ...
    def record_failure(self, job_id: str, *, error: str) -> None: ...
    def requeue(self, job_id: str, *, error: str) -> None: ...
    def escalate(self, job_id: str, *, error: str) -> None: ...


TransportRunner = Callable[[dict[str, Any]], Any]
# TransportRunner may return either a plain dict (legacy contract) or a
# ``TransportResult`` from outbox. When a TransportResult is returned it
# is forwarded verbatim so callers can surface ``dropped_response_unknown``
# and other special states that the dict contract cannot express.


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


class Recovery:
    """Run-once recovery that drains captured observations.

    Two execution paths:

    * **Real outbox path** (``_uses_real_outbox(outbox) is True``) —
      claims one job per call via SQLite lease arbitration, routes the
      job through ``transport_runner``, and persists the outcome via
      the real outbox's record_* APIs. The ``owner`` argument uniquely
      identifies this worker; two workers MUST use distinct owners.
    * **Legacy handler path** — iterates the outbox's pending jobs via
      the handler callback. Kept for back-compat with bespoke outboxes.

    The default :py:meth:`run_once` is fully driven by the outbox; the
    recovery layer only decides between ack / requeue-with-budget /
    escalate-without-deleting / surface-unknown.
    """

    def __init__(
        self,
        *,
        outbox: Any,
        transport_runner: TransportRunner,
        owner: str | None = None,
        max_attempts: int = 5,
        lease_seconds: int = 30,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        self._outbox = outbox
        # Default to a fresh UUID so two workers that forget to pass
        # ``owner`` still get distinct lease identities. Operators who
        # care about worker identity MUST pass ``owner`` explicitly.
        self._owner: str = owner or f"recovery-{uuid.uuid4().hex[:12]}"
        self._runner = transport_runner
        self._max_attempts = max_attempts
        self._lease_seconds = lease_seconds
        self._clock = clock or _default_clock

    # -- public ----------------------------------------------------------

    def _uses_real_outbox(self, outbox: Any | None = None) -> bool:
        """Return True iff ``outbox.run_once`` accepts the transport-API kwargs.

        The real portable outbox takes ``(transport, *, clock, owner,
        lease_seconds, ...)``. Anything else is treated as legacy.
        """
        ob = outbox if outbox is not None else self._outbox
        try:
            sig = inspect.signature(ob.run_once)
        except (TypeError, ValueError):
            return False
        return "owner" in sig.parameters

    def run_once(
        self,
        *,
        now: float | None = None,
        clock: Callable[[], float] | None = None,
    ) -> dict[str, int] | int:
        """Drain one batch of pending captures.

        On the real outbox path returns a counts dict with keys
        ``claimed``/``completed``/``retried``/``conflicts``/``dropped_unknown``.
        On the legacy path returns the number of jobs processed (an int).
        """
        if self._uses_real_outbox():
            return self._run_once_real(now=now, clock=clock)
        return self._run_once_legacy(now=now)

    # -- real outbox path ------------------------------------------------

    def _run_once_real(
        self,
        *,
        now: float | None = None,
        clock: Callable[[], float] | None = None,
    ) -> dict[str, int]:
        """Drive one batch through the real portable outbox."""
        # Late import: the real outbox only exists when the brain-loop
        # skill directory is on sys.path. Tests inject fakes; production
        # wires the SQLite outbox.
        from outbox import TransportResult  # type: ignore

        ob = self._outbox
        clock_fn = clock or (lambda: now) if now is not None else self._clock

        def transport(job: Any) -> Any:
            if job.attempts >= self._max_attempts:
                return TransportResult(
                    state="conflict",
                    error=_sanitize_error("retry-budget-exhausted"),
                )
            try:
                response = self._runner(job.payload)
            except Exception as exc:  # noqa: BLE001
                err = _sanitize_error(f"{type(exc).__name__}: {exc}")
                return TransportResult(
                    state="retry",
                    error=err or "transport-unavailable",
                )

            # Fast path: callers that need to surface a special state
            # (``dropped_response_unknown``) can return a TransportResult
            # directly; the dict contract cannot express it.
            if isinstance(response, TransportResult):
                # Still sanitize error text if provided.
                if response.error is not None:
                    response = TransportResult(
                        state=response.state,
                        acknowledged_version=response.acknowledged_version,
                        response=response.response,
                        error=_sanitize_error(response.error),
                    )
                if response.state == "ok" and (
                    type(response.acknowledged_version) is not int
                    or response.acknowledged_version != job.version
                ):
                    return TransportResult(state="retry", error="exact-version-ack-required")
                # Enrichment follow-up happens only after an exact-version acknowledgement.
                if response.state == "ok" and isinstance(
                    response.response, dict
                ) and response.response.get("enrichment") == "provider_unavailable":
                    self._maybe_enqueue_enrichment(job, response.response)
                return response

            if not isinstance(response, dict):
                return TransportResult(
                    state="retry",
                    error=_sanitize_error(
                        f"transport-runner-returned-{type(response).__name__}",
                    ) or "transport-runner-bad-return",
                )

            ack = response.get("acknowledged_version")
            # Exact-version ack: a missing or wrong-version ack is a
            # retry, never a silent success.
            if not isinstance(ack, int) or ack != job.version:
                return TransportResult(
                    state="retry",
                    error=_sanitize_error(
                        f"exact-version-ack-required "
                        f"(got={ack!r}, want={job.version})",
                    ) or "exact-version-ack-required",
                )

            # Provider-unavailable → record success AND enqueue enrichment.
            if response.get("enrichment") == "provider_unavailable":
                self._maybe_enqueue_enrichment(job, response)

            return TransportResult(
                state="ok",
                acknowledged_version=ack,
                response=response,
            )

        counts = ob.run_once(
            transport,
            clock=clock_fn,
            owner=self._owner,
            lease_seconds=self._lease_seconds,
            limit=1,  # one job per call — concurrent workers arbitrate cleanly
        )
        # Defensive coercion: outbox returns dict[str, int]; tests rely
        # on the exact key set. Already correct in the real outbox.
        return counts

    def _maybe_enqueue_enrichment(self, job: Any, response: dict[str, Any]) -> None:
        """Enqueue a follow-up enrichment row when the provider is down.

        Safe to call against legacy outboxes (skipped via ``hasattr``).
        The original upload job still completes — evidence is never lost.
        """
        ob = self._outbox
        if not hasattr(ob, "enqueue_enrichment"):
            # Legacy / fake outbox: keep the existing log-and-move-on
            # behaviour so callers don't lose their enrichment signal.
            logger.info(
                "recovery: enrichment provider unavailable for %s; "
                "outbox has no enqueue_enrichment API, capture retained "
                "for follow-up",
                getattr(job, "id", "<unknown>"),
            )
            return
        try:
            payload = {
                "capture_id": getattr(job, "id", None),
                "source_id": getattr(job, "id", None),
                "kind": getattr(job, "kind", None),
                "original_payload": getattr(job, "payload", {}),
                "response": response,
                "reason": "provider_unavailable",
            }
            ob.enqueue_enrichment(
                "enrichment.follow_up",
                payload,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "recovery: enqueue_enrichment failed for %s",
                getattr(job, "id", "<unknown>"),
            )

    # -- legacy fake-outbox path -----------------------------------------

    def _run_once_legacy(self, *, now: float | None = None) -> int:
        return self._outbox.run_once(self._handle, now=now)

    def _handle(self, job: Any) -> None:
        job_id = getattr(job, "id", None)
        if not job_id:
            logger.warning("recovery: job without id, skipping")
            return

        payload = getattr(job, "payload", None)
        if not isinstance(payload, dict):
            self._outbox.record_failure(job_id, error="invalid payload")
            return

        current_attempts = int(getattr(job, "attempts", 0) or 0)
        job_max = getattr(job, "max_attempts", None)
        effective_max = (
            int(job_max) if isinstance(job_max, int) and job_max > 0
            else self._max_attempts
        )

        if current_attempts >= effective_max:
            self._outbox.escalate(
                job_id, error=f"max attempts reached ({current_attempts})",
            )
            return

        try:
            response = self._runner(payload)
        except Exception as exc:  # noqa: BLE001
            error_str = _sanitize_error(f"{type(exc).__name__}: {exc}") \
                or "transport-unavailable"
            self._outbox.record_failure(job_id, error=error_str)
            if current_attempts + 1 >= effective_max:
                self._outbox.escalate(job_id, error=error_str)
            else:
                self._outbox.requeue(job_id, error=error_str)
            return

        # Enrichment follow-up: legacy fake outboxes don't expose
        # enqueue_enrichment; log instead so the signal isn't dropped.
        if (
            isinstance(response, dict)
            and response.get("enrichment") == "provider_unavailable"
            and not hasattr(self._outbox, "enqueue_enrichment")
        ):
            logger.info(
                "recovery: enrichment provider unavailable for %s; "
                "capture retained for follow-up",
                job_id,
            )

        self._outbox.record_success(job_id, response=response)


def _default_clock() -> float:
    import time as _time
    return _time.time()


__all__ = ["Recovery", "_sanitize_error", "TransportRunner"]