"""Task 4 — capture layer for tool-call observations.

Capture is intentionally independent of the real outbox: it accepts an
injectable ``sink`` (a callable that takes a record dict). Tests use an
in-memory fake; production wires the durable outbox via
``recovery.Recovery``.

Design contract (from the Task 4 brief):

* **Stable, dedup'd id** — derived from trusted context (invocation_id,
  session_id, occurred_at). Missing values do not raise; the capture
  layer fills them deterministically from the injected clock or marks
  them absent.
* **Targeted context only** — tool_name, args, result, error, project,
  timing. No transcripts, no model, no network payloads.
* **Sanitized** — structured secrets (``api_key``, ``token``, …) are
  redacted before persistence. The redact key set is injected so
  callers can extend it.
* **Honest about errors / interruption / unknown** — the result_state
  field reports ``ok``, ``error``, ``interrupted``, or ``unknown``.
* **Sink failure is contained** — a failing persist/enqueue never
  crashes the plugin framework.
* **Portable hook adapter** — :class:`HookAdapter` exposes
  ``register(ctx)`` and wires a single ``post_tool_call`` callback so
  the plugin can be dropped into any Hermes plugin slot. It does NOT
  claim that hooks are installed or enabled beyond registration.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any, Callable, Iterable, Mapping


logger = logging.getLogger(__name__)


# Result states — explicit so callers cannot infer from ad-hoc None checks.
RESULT_OK = "ok"
RESULT_ERROR = "error"
RESULT_INTERRUPTED = "interrupted"
RESULT_UNKNOWN = "unknown"


# Default structured-secret keys to redact. Callers may extend.
DEFAULT_REDACT_KEYS: frozenset[str] = frozenset({
    "api_key", "apikey", "authorization", "auth", "token", "password",
    "secret", "private_key", "session_token", "bearer",
})


def _coerce_occurred_at(value: Any, *, clock: Callable[[], float]) -> float:
    """Return a numeric occurred_at or the injected clock's now."""
    if value is None:
        return clock()
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)  # last resort: parse strings like ISO-8601 offsets
    except (TypeError, ValueError):
        return clock()


def _derive_capture_id(
    *,
    invocation_id: str | None,
    session_id: str | None,
    occurred_at: float,
    tool_name: str,
) -> str:
    """Stable UUID5 keyed on trusted context. Missing fields become ''."""
    material = "|".join([
        invocation_id or "",
        session_id or "",
        f"{occurred_at:.6f}",
        tool_name or "",
    ])
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return str(uuid.UUID(bytes=digest[:16]))


def _redact(value: Any, *, keys: frozenset[str]) -> Any:
    """Recursively redact structured secrets. Free-text is left alone."""
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in keys:
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v, keys=keys)
        return out
    if isinstance(value, list):
        return [_redact(v, keys=keys) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact(v, keys=keys) for v in value)
    return value


def _classify_result(*, result: Any, error: Any, interrupted: bool) -> str:
    if interrupted:
        return RESULT_INTERRUPTED
    if error is not None:
        return RESULT_ERROR
    if result is None:
        return RESULT_UNKNOWN
    return RESULT_OK


def _safe_json_default(value: Any) -> Any:
    """Last-resort serializer for non-JSON values."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return repr(value)
    return repr(value)


class AgentCapture:
    """Capture layer — pure function over a sink.

    ``sink`` is anything callable taking a dict. The real outbox is wired
    in production; tests inject an in-memory recorder.
    """

    def __init__(
        self,
        *,
        sink: Callable[[dict[str, Any]], None],
        redact_keys: Iterable[str] = DEFAULT_REDACT_KEYS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._sink = sink
        self._redact_keys = frozenset(k.lower() for k in redact_keys)
        self._clock: Callable[[], float] = clock or _default_clock

    # -- public ----------------------------------------------------------

    def handle_post_tool_call(self, context: Mapping[str, Any]) -> str:
        """Process a single post_tool_call event. Returns the capture id.

        Never raises: a sink failure is logged and swallowed so the
        plugin framework keeps running.
        """
        if not isinstance(context, Mapping):
            logger.warning("capture: non-mapping context %r", type(context).__name__)
            context = {"_raw": context}

        invocation_id = context.get("invocation_id")
        session_id = context.get("session_id")
        occurred_at = _coerce_occurred_at(context.get("occurred_at"), clock=self._clock)
        tool_name = str(context.get("tool_name") or "")
        project_id = context.get("project_id")  # nullable / missing tolerated

        capture_id = _derive_capture_id(
            invocation_id=invocation_id if isinstance(invocation_id, str) else None,
            session_id=session_id if isinstance(session_id, str) else None,
            occurred_at=occurred_at,
            tool_name=tool_name,
        )

        result_state = _classify_result(
            result=context.get("result"),
            error=context.get("error"),
            interrupted=bool(context.get("interrupted")),
        )

        record: dict[str, Any] = {
            "id": capture_id,
            "kind": "tool.completed",
            "invocation_id": invocation_id,
            "session_id": session_id,
            "occurred_at": occurred_at,
            "project_id": project_id,
            "tool_name": tool_name,
            "result_state": result_state,
            "args": _redact(context.get("args") or {}, keys=self._redact_keys),
            "result": _redact(context.get("result"), keys=self._redact_keys),
            "error": context.get("error"),
        }

        # Belt-and-suspenders: strip transcript / model / network if a caller
        # # accidentally passes them in the top-level context.
        for forbidden in ("messages", "transcript", "model", "network",
                          "api_key", "apiKey"):
            record.pop(forbidden, None)

        try:
            self._sink(record)
        except Exception as exc:  # noqa: BLE001 — capture MUST NOT raise
            logger.warning(
                "capture sink failed for %s: %s", capture_id, exc,
                exc_info=True,
            )
        return capture_id


def _default_clock() -> float:
    import time as _time
    return _time.time()


class HookAdapter:
    """Portable adapter to wire capture into a Hermes plugin slot.

    Usage from a plugin::

        from agent_capture import AgentCapture, HookAdapter

        def register(ctx):
            capture = AgentCapture(sink=my_sink)
            HookAdapter(capture=capture).register(ctx)
    """

    def __init__(self, *, capture: AgentCapture) -> None:
        self._capture = capture

    def register(self, ctx: Any) -> None:
        """Register the post_tool_call callback on the plugin context.

        No other side effects: this adapter does NOT claim hooks are
        installed or enabled beyond registration, and does not perform
        any I/O of its own.
        """
        register_hook = getattr(ctx, "register_hook", None)
        if register_hook is None:
            raise TypeError(
                "HookAdapter.register: ctx has no register_hook method"
            )
        register_hook("post_tool_call", self._on_post_tool_call)

    # -- internal --------------------------------------------------------

    def _on_post_tool_call(self, *args: Any, **kwargs: Any) -> None:
        """Normalize the various call shapes the runtime may use."""
        context = self._normalize(args, kwargs)
        self._capture.handle_post_tool_call(context)

    @staticmethod
    def _normalize(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
        """Accept positional or keyword invocation.

        Plugins see varying shapes depending on the runtime path
        (gateway, CLI, desktop). All of the following are tolerated:

        * ``on_post_tool_call(tool_name, args_dict, result, **kwargs)``
        * ``on_post_tool_call(context=Mapping)``
        * ``on_post_tool_call(event)`` where ``event`` has ``.payload``
        """
        if "context" in kwargs and isinstance(kwargs["context"], Mapping):
            return dict(kwargs["context"])

        if args and isinstance(args[0], Mapping):
            return dict(args[0])

        # Positional: tool_name, args, result, ...
        if len(args) >= 1 and isinstance(args[0], str):
            tool_name = args[0]
            tool_args = args[1] if len(args) >= 2 else {}
            result = args[2] if len(args) >= 3 else None
            ctx: dict[str, Any] = {
                "tool_name": tool_name,
                "args": tool_args,
                "result": result,
            }
            # Promote known observability ids from kwargs if present
            for key in ("invocation_id", "session_id", "occurred_at",
                        "project_id", "error", "interrupted"):
                if key in kwargs:
                    ctx[key] = kwargs[key]
            return ctx

        # Object-style event with .payload attribute
        if args and hasattr(args[0], "payload"):
            payload = getattr(args[0], "payload", {})
            if isinstance(payload, Mapping):
                return dict(payload)
            return {"_raw_payload": payload}

        # Last resort: collect kwargs (skip private)
        return {k: v for k, v in kwargs.items() if not k.startswith("_")}
