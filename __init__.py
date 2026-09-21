"""Hermes Agent plugin for Brain shared experience."""
from __future__ import annotations

import importlib.util
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


def register(ctx) -> None:
    """Register the Brain skill, prompt discovery hint, and non-blocking lifecycle hooks."""
    adapter = _load_adapter()
    ctx.register_skill("brain-loop", SKILL)
    ctx.register_system_prompt_section(
        "brain-loop",
        (
            "Brain shared experience is available through the plugin skill `brain:brain-loop`. "
            "For substantial debugging, configuration, or reusable decisions, load that skill, "
            "retrieve relevant experience before acting, and report honest outcomes after verification. "
            "Automatic hooks record sanitized tool-event facts; they do not replace retrieval, outcome, "
            "or evidence-backed proposal decisions."
        ),
        position="after_memory",
        max_chars=700,
    )
    ctx.register_hook("post_tool_call", adapter.post_tool_call)
    ctx.register_hook("on_session_finalize", adapter.on_session_finalize)
    ctx.register_hook("on_session_reset", adapter.on_session_reset)
