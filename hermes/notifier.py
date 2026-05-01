"""Telegram notification service for the Hermes system.

Provides best-effort notifications via the Telegram Bot API using only
stdlib (urllib.request) so no extra HTTP dependencies are required.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TelegramNotifier
# ---------------------------------------------------------------------------

_EVENT_TEMPLATES: dict[str, str] = {
    "pending_new": (
        "<b>📝 New Proposal — Needs Review</b>\n"
        "Proposal: <code>{proposal_id}</code>\n"
        "Category: {category}\n"
        "Project: <code>{project_key}</code>\n"
        "Summary: {summary}"
    ),
    "auto_approved": (
        "<b>✅ Auto-Approved (Low Risk)</b>\n"
        "Proposal: <code>{proposal_id}</code>\n"
        "Category: {category}"
    ),
    "duplicate_detected": (
        "<b>🔄 Semantic Duplicate Detected</b>\n"
        "New: <code>{new_id}</code>\n"
        "Original: <code>{original_id}</code>\n"
        "Suggested memory: {suggested_memory}"
    ),
    "health_alert": (
        "<b>⚠️ Health Alert</b>\n"
        "Type: {alert_type}\n"
        "Message: {message}"
    ),
    "export_rebuilt": (
        "<b>📦 Export Rebuilt</b>\n"
        "Scope: {scope}\n"
        "Project: <code>{project_key}</code>\n"
        "Size: {size_bytes} bytes"
    ),
    "eviction_performed": (
        "<b>🗑️ Proposal Evicted</b>\n"
        "Proposal: <code>{proposal_id}</code>\n"
        "Reason: {reason}\n"
        "New state: {new_state}"
    ),
}


class TelegramNotifier:
    """Sends formatted notifications to a Telegram chat via the Bot API."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    # -- public properties ---------------------------------------------------

    @property
    def enabled(self) -> bool:
        """True when both bot_token and chat_id are non-empty."""
        return bool(self._bot_token and self._chat_id)

    # -- low-level send ------------------------------------------------------

    async def send(self, text: str) -> bool:
        """POST *text* to the Telegram sendMessage endpoint.

        Returns True on success, False on any failure.
        Never raises — notifications are best-effort.
        """
        import html as _html

        if not self.enabled:
            return False

        # Strip any stray HTML tags from user content to prevent 400 errors.
        # Telegram parse_mode=HTML is strict about matching tags.
        safe_text = _html.escape(text)
        # Re-enable intentional HTML tags that we format ourselves.
        for tag in ("b", "i", "u", "s", "code", "pre", "a"):
            safe_text = safe_text.replace(f"&lt;{tag}&gt;", f"<{tag}>")
            safe_text = safe_text.replace(f"&lt;/{tag}&gt;", f"</{tag}>")

        url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
        payload = json.dumps({
            "chat_id": self._chat_id,
            "text": safe_text,
            "parse_mode": "HTML",
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status < 300:
                    return True
                logger.warning("Telegram responded with status %s", resp.status)
                return False
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send Telegram notification")
            return False

    # -- high-level event formatter ------------------------------------------

    async def notify(self, event: str, details: dict) -> bool:
        """Format *event* using *details* and dispatch via :meth:`send`.

        Unknown events are sent as a simple key-value dump so nothing is
        silently swallowed.  Returns the result of :meth:`send`.
        """
        template = _EVENT_TEMPLATES.get(event)
        if template is not None:
            try:
                text = template.format_map(details)
            except KeyError:
                logger.exception("Missing key(s) for event %s template", event)
                text = f"<b>{event}</b>\n{details}"
        else:
            text = f"<b>{event}</b>\n{details}"

        return await self.send(text)


# ---------------------------------------------------------------------------
# NotificationRouter
# ---------------------------------------------------------------------------

class NotificationRouter:
    """Single entry-point the rest of the codebase uses to dispatch events."""

    def __init__(self, notifier: TelegramNotifier | None = None) -> None:
        self._notifier = notifier

    def dispatch(self, event: str, details: dict) -> None:
        """Fire-and-forget notification dispatch.

        If there is no notifier or it is not enabled this returns silently.
        Failures are logged by the notifier but never propagated.
        """
        if self._notifier is None or not self._notifier.enabled:
            return

        # Schedule the coroutine but don't await it — truly fire-and-forget.
        # We create a Task on the running loop if there is one, otherwise
        # fall back to a synchronous best-effort call via urllib.
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            loop.create_task(self._notifier.notify(event, details))
        except RuntimeError:
            # No running event-loop (e.g. called from sync code outside async).
            # Run the coroutine in a throwaway event loop.
            try:
                import asyncio
                asyncio.run(self._notifier.notify(event, details))
            except Exception:  # noqa: BLE001
                logger.exception("Notification dispatch failed (sync fallback)")
        except Exception:  # noqa: BLE001
            logger.exception("Notification dispatch failed (async)")
