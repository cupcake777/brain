"""Generate JSON Schema artefacts and validate bundled fixtures.

Run from the repository root:

    .venv/bin/python -m hermes.contracts_schemas

It writes the schema artefacts to
``skills/brain-loop/references/schemas/`` and ensures the bundled draft +
complete fixtures validate against the proposal schema when ``jsonschema``
is installed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / "skills" / "brain-loop" / "references" / "schemas"
FIXTURES_DIR = SCHEMAS_DIR.parent / "fixtures"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hermes.contracts import (  # noqa: E402  (sys.path adjusted above)
    ExecutionEvent,
    KnowledgeDirectiveInput,
    KnowledgeRevision,
    ProposalRevision,
    SourceRef,
)


SCHEMA_TARGETS = (
    (ExecutionEvent, "execution_event.schema.json"),
    (ProposalRevision, "proposal_revision.schema.json"),
    (SourceRef, "source_ref.schema.json"),
    (KnowledgeRevision, "knowledge_revision.schema.json"),
)


def _ensure_directories() -> None:
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)


def _write_schema(model: type, filename: str) -> Path:
    schema = model.model_json_schema()
    target = SCHEMAS_DIR / filename
    target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _write_proposal_fixtures() -> tuple[Path, Path]:
    """Bundled fixtures for proposal-revision validation.

    These are intentionally hand-shaped so that they exercise the same
    wire-format the server would accept, not a Python dump of an instance.
    """

    draft = {
        "$comment": "Minimal revision 1 draft; only IDs and provenance.",
        "id": "11111111-1111-4111-8111-111111111111",
        "version": 1,
        "project_id": None,
        "agent_id": "agent-fixture",
        "occurred_at": None,
        "target_id": None,
        "action": None,
        "result": None,
        "lesson": None,
        "draft": True,
        "source_refs": [],
    }

    complete = {
        "$comment": "Revision 1 ready proposal with one execution source ref.",
        "id": "22222222-2222-4222-8222-222222222222",
        "version": 1,
        "project_id": "brain",
        "agent_id": "agent-fixture",
        "occurred_at": "2026-09-17T08:00:00Z",
        "target_id": "ops/brain",
        "action": "Apply atomic config replacement before restarting daemons.",
        "result": "Restart succeeded with zero downtime; previous bug avoided.",
        "lesson": "Use atomic config replace before restarting daemons",
        "draft": False,
        "source_refs": [
            {
                "type": "execution",
                "id": "33333333-3333-4333-8333-333333333333",
            }
        ],
    }

    draft_path = FIXTURES_DIR / "proposal-draft.json"
    complete_path = FIXTURES_DIR / "proposal-complete.json"
    draft_path.write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    complete_path.write_text(json.dumps(complete, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return draft_path, complete_path


def _validate_against_schema(payload_path: Path, schema_path: Path) -> None:
    """Validate the bundled fixture against the model and the schema.

    The strict Pydantic model is the source of truth — it always runs and
    enforces whitespace rejection, field maxima and the ready/draft
    cross-field rules that JSON Schema cannot express.  When the optional
    ``jsonschema`` package is installed the wire-format JSON Schema
    artefact is cross-checked as well.  ``$comment`` keys are JSON Schema
    documentation markers; they are stripped before Pydantic validation
    because the contracts use ``extra=forbid``.
    """

    raw = payload_path.read_text(encoding="utf-8")
    payload = json.loads(raw)

    # Strip JSON Schema documentation markers — they are not part of the
    # wire contract and ``extra=forbid`` would reject them.
    payload.pop("$comment", None)

    # Always validate against the Pydantic model — the contract truth.
    ProposalRevision.model_validate(payload)

    try:
        import jsonschema  # type: ignore
    except ImportError:
        return

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)


def main() -> int:
    _ensure_directories()
    for model, filename in SCHEMA_TARGETS:
        _write_schema(model, filename)
    _write_proposal_fixtures()
    schema_path = SCHEMAS_DIR / "proposal_revision.schema.json"
    for fixture in (
        FIXTURES_DIR / "proposal-draft.json",
        FIXTURES_DIR / "proposal-complete.json",
    ):
        _validate_against_schema(fixture, schema_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())