"""Hermes Agent plugin for Brain shared experience."""
from __future__ import annotations

import importlib.util
import json
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "skills" / "brain-loop" / "SKILL.md"
ADAPTER = ROOT / "skills" / "brain-loop" / "scripts" / "brain_plugin.py"


def _load_adapter():
    spec = importlib.util.spec_from_file_location("brain_hermes_plugin_adapter", ADAPTER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Brain Hermes adapter could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prompt_section(session_info: Mapping[str, object]) -> str:
    session_id = str(session_info.get("session_id") or "").strip()[:200]
    session_hint = (
        f"Use session_id={json.dumps(session_id, ensure_ascii=False)} for retrieval and finalization. "
        if session_id else "Pass the real session ID for retrieval and finalization. "
    )
    return (
        "Brain shared experience is available through the plugin skill `brain:brain-loop`. "
        "For substantial debugging, configuration, or reusable decisions, load that skill. "
        "Do not retrieve for trivial tasks. When available, use retrieve_knowledge, "
        "report_knowledge_outcome after verification, and finalize_knowledge_session at completion; "
        "otherwise use the skill client with the same real session ID. "
        + session_hint
        + "Report honest outcomes for returned candidates. Automatic hooks capture sanitized "
        "tool events; propose reusable lessons only with verified evidence."
    )


def register(ctx) -> None:
    """Register the Brain skill, prompt discovery hint, and non-blocking lifecycle hooks."""
    adapter = _load_adapter()
    ctx.register_skill("brain-loop", SKILL)
    ctx.register_system_prompt_section(
        "brain-loop", _prompt_section, position="after_memory", max_chars=2000,
    )
    ctx.register_hook("post_tool_call", adapter.post_tool_call)
    ctx.register_hook("on_session_finalize", adapter.on_session_finalize)
    ctx.register_hook("on_session_reset", adapter.on_session_reset)
