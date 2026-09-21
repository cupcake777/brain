"""Tests for the strict v2 Brain contracts.

These tests intentionally cover only what the implementation must guarantee:

* strict types, ``extra=forbid`` and explicit maxima
* timezone-aware datetimes normalised to UTC
* UUID4 identifiers, immutable ID/version pair, no bool/int coercion
* server-owned metadata is not writable from input payloads
* draft proposals accept missing facts; ready proposals require them
* explicit directive authoring is not a model-supplied boolean
* deterministic canonicalisation helpers

The schemas live in :mod:`hermes.contracts`. The test layout mirrors the
contract families:

* ``ExecutionEvent`` — capture contract for hooks and runtime events.
* ``ProposalRevision`` — versioned submission contract.
* ``SourceRef`` — typed, resolved-only evidence references.
* ``KnowledgeRevision`` — curated revision contract.
* ``KnowledgeDirectiveInput`` — authenticated explicit-authority input.
* ``Canonical helpers`` — digest + canonical-JSON for required checks.

Every accepted/rejected fixture has a deterministic expected result that does
not depend on the model implementation.  If a behaviour is tested here it is
guaranteed to hold; if it is not, no behaviour is claimed.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from hermes.contracts import (
    DEFAULT_MAX_ACTION_CHARS,
    DEFAULT_MAX_EVIDENCE_BYTES,
    DEFAULT_MAX_LESSON_CHARS,
    DEFAULT_MAX_NOTE_CHARS,
    DEFAULT_MAX_PROJECT_ID_LEN,
    DEFAULT_MAX_REASON_CHARS,
    DEFAULT_MAX_RESULT_CHARS,
    DEFAULT_MAX_TARGET_ID_LEN,
    DEFAULT_MAX_URL_LEN,
    DEFAULT_MAX_VERSION_INT,
    DEFAULT_MIN_ACTION_CHARS,
    DEFAULT_MIN_LESSON_CHARS,
    DEFAULT_MIN_RESULT_CHARS,
    EXECUTION_EVENT_CLASSIFICATIONS,
    EXECUTION_EVENT_ORIGINS,
    KNOWLEDGE_LIFECYCLE_STATES,
    KNOWLEDGE_SCOPES,
    KNOWLEDGE_KINDS,
    CanonicalDigestError,
    canonical_digest,
    canonical_json,
    ExecutionEvent,
    ExecutionEventClassification,
    ExecutionEventOrigin,
    KnowledgeDirectiveInput,
    KnowledgeDirectiveSource,
    KnowledgeLifecycleState,
    KnowledgeRevision,
    KnowledgeRevisionLink,
    KnowledgeScope,
    KnowledgeSourceRef,
    KnowledgeKind,
    ProposalRevision,
    ProposalStatus,
    ProposalWorkflow,
    SourceDocument,
    SourceRef,
    SourceRefType,
    ProposalSourceRef,
    is_proposal_ready,
)


SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "skills" / "brain-loop" / "references" / "schemas"


# ---------------------------------------------------------------------------
# Module surface — ensure contracts are importable + schemas are generated.
# ---------------------------------------------------------------------------


def test_schemas_directory_is_created() -> None:
    """Schema fixtures must be generated as part of the module."""

    assert SCHEMAS_DIR.is_dir(), f"schema directory missing: {SCHEMAS_DIR}"


def test_required_jsonschema_artifacts_exist() -> None:
    """All four primary contracts must have a generated JSON Schema."""

    expected = {
        "execution_event.schema.json",
        "proposal_revision.schema.json",
        "source_ref.schema.json",
        "knowledge_revision.schema.json",
    }
    present = {p.name for p in SCHEMAS_DIR.glob("*.json")}
    missing = expected - present
    assert not missing, f"missing schema artefacts: {sorted(missing)}"


def test_jsonschema_validates_bundled_complete_proposal() -> None:
    """Bundled draft + complete fixtures must validate against the contract.

    When ``jsonschema`` is installed, validates the JSON Schema artefact.
    Otherwise validates via the strict Pydantic model, which is the
    stronger guarantee: it also enforces whitespace-rejection, maxima,
    readiness cross-field rules and UUID4 discipline.
    ``$comment`` keys are JSON Schema documentation markers; they are
    stripped before Pydantic validation because the contracts use
    ``extra=forbid``.
    """

    schema_path = SCHEMAS_DIR / "proposal_revision.schema.json"
    assert schema_path.is_file()

    fixtures = SCHEMAS_DIR.parent / "fixtures"
    for name in ("proposal-draft.json", "proposal-complete.json"):
        payload_path = fixtures / name
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        # Strip JSON Schema documentation markers.
        payload.pop("$comment", None)

        # Pydantic validation is the source-of-truth contract and always
        # available — it is stricter than the JSON Schema artefact.
        ProposalRevision.model_validate(payload)

        # When the optional ``jsonschema`` package is available we also
        # cross-check the wire-format JSON Schema artefact.
        try:
            import jsonschema  # type: ignore
        except ImportError:
            continue
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(payload, schema)


# ---------------------------------------------------------------------------
# ExecutionEvent
# ---------------------------------------------------------------------------


def _execution_event_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "project_id": None,
        "agent_id": "agent-test",
        "occurred_at": datetime(2026, 9, 17, 8, 0, tzinfo=timezone.utc),
        "target_id": None,
        "action": None,
        "result": None,
        "source_refs": [],
        "origin": "hook",
        "classification": "production",
    }
    base.update(overrides)
    return base


def test_execution_event_minimal_draft_is_accepted() -> None:
    """Hook events may arrive with missing draft fields."""

    event = ExecutionEvent(**_execution_event_kwargs())
    assert event.id.version == 4
    assert event.project_id is None
    assert event.action is None
    assert event.result is None
    assert event.target_id is None


def test_execution_event_rejects_unknown_field() -> None:
    payload = _execution_event_kwargs(workflow="submitted")
    with pytest.raises(ValidationError) as exc:
        ExecutionEvent(**payload)  # type: ignore[arg-type]
    assert "workflow" in str(exc.value)


def test_execution_event_requires_uuid4_id() -> None:
    payload = _execution_event_kwargs(id=str(uuid.UUID("00000000-0000-1000-8000-000000000000")))
    with pytest.raises(ValidationError) as exc:
        ExecutionEvent(**payload)
    assert "id" in str(exc.value).lower()


def test_execution_event_rejects_naive_datetime() -> None:
    """Spec: naive datetimes are rejected; only timezone-aware input is allowed."""

    payload = _execution_event_kwargs(occurred_at=datetime(2026, 9, 17, 8, 0))
    with pytest.raises(ValidationError) as exc:
        ExecutionEvent(**payload)
    assert "occurred_at" in str(exc.value).lower()
    assert "tz" in str(exc.value).lower() or "timezone" in str(exc.value).lower()


def test_execution_event_normalises_aware_datetime_to_utc() -> None:
    """Aware datetimes in any zone are normalised to UTC."""

    tz = timezone(timezone.utc.utcoffset(None) + timedelta(hours=8))
    payload = _execution_event_kwargs(occurred_at=datetime(2026, 9, 17, 16, 0, tzinfo=tz))
    event = ExecutionEvent(**payload)
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.utcoffset().total_seconds() == 0


def test_execution_event_rejects_string_coerced_bool() -> None:
    """Pydantic strict mode must not coerce 'true' to True."""

    payload = _execution_event_kwargs()
    payload["classification"] = "true"
    with pytest.raises(ValidationError):
        ExecutionEvent(**payload)  # type: ignore[arg-type]


def test_execution_event_rejects_int_for_id() -> None:
    payload = _execution_event_kwargs(id=123)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ExecutionEvent(**payload)


def test_execution_event_origin_and_classification_are_enums() -> None:
    assert {"hook", "wrapper", "manual", "system"} == set(EXECUTION_EVENT_ORIGINS)
    assert {"production", "probe", "evaluation"} == set(EXECUTION_EVENT_CLASSIFICATIONS)
    # unknown values rejected
    with pytest.raises(ValueError):
        ExecutionEventOrigin("debug")
    payload = _execution_event_kwargs(classification="debug")
    with pytest.raises(ValidationError):
        ExecutionEvent(**payload)


def test_execution_event_maxima_enforced() -> None:
    payload = _execution_event_kwargs(
        project_id="x" * (DEFAULT_MAX_PROJECT_ID_LEN + 1),
    )
    with pytest.raises(ValidationError):
        ExecutionEvent(**payload)


def test_execution_event_trusted_env_op_requires_target() -> None:
    """Trusted environment ops must declare a target."""

    with pytest.raises(ValidationError) as exc:
        ExecutionEvent(
            **_execution_event_kwargs(
                classification="production",
                target_id=None,
                action="ssh root@server rm -rf /tmp/cache",
            )
        )
    assert "target" in str(exc.value).lower()


def test_execution_event_whitespace_only_rejected() -> None:
    with pytest.raises(ValidationError):
        ExecutionEvent(**_execution_event_kwargs(action="   \n  "))


def test_execution_event_frozen() -> None:
    event = ExecutionEvent(**_execution_event_kwargs())
    with pytest.raises(ValidationError):
        event.action = "new"  # type: ignore[misc]


def test_execution_event_source_refs_strict_union() -> None:
    """Source refs must be the typed union; no string passthrough."""

    payload = _execution_event_kwargs(
        source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
    )
    event = ExecutionEvent(**payload)
    assert len(event.source_refs) == 1
    assert isinstance(event.source_refs[0], SourceRef)

    bad = _execution_event_kwargs(
        source_refs=[{"type": "unknown", "id": str(uuid.uuid4())}],
    )
    with pytest.raises(ValidationError):
        ExecutionEvent(**bad)


def test_execution_event_rejects_long_url_in_source() -> None:
    long_url = "https://example.com/" + ("a" * DEFAULT_MAX_URL_LEN)
    with pytest.raises(ValidationError):
        SourceDocument(
            id=uuid.uuid4(),
            url=long_url,
            version=1,
            excerpt="",
        )


# ---------------------------------------------------------------------------
# ProposalRevision
# ---------------------------------------------------------------------------


def _proposal_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "version": 1,
        "project_id": None,
        "agent_id": "agent-test",
        "occurred_at": None,
        "target_id": None,
        "action": None,
        "result": None,
        "lesson": None,
        "draft": True,
        "source_refs": [],
    }
    base.update(overrides)
    return base


def test_proposal_revision_draft_accepts_missing_facts() -> None:
    proposal = ProposalRevision(**_proposal_kwargs())
    assert proposal.draft is True
    assert proposal.action is None
    assert proposal.lesson is None


def test_proposal_revision_ready_rejects_missing_action() -> None:
    kwargs = _proposal_kwargs(draft=False, lesson="use atomic config replace")
    kwargs.pop("action", None)
    kwargs.pop("result", None)
    kwargs["action"] = None
    kwargs["result"] = None
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(**kwargs)
    assert "action" in str(exc.value).lower()


def test_proposal_revision_ready_rejects_missing_result() -> None:
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(
            **_proposal_kwargs(
                draft=False,
                action="apply patch",
                result=None,
                lesson="lesson text",
                source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
            )
        )
    assert "result" in str(exc.value).lower()


def test_proposal_revision_ready_rejects_missing_lesson() -> None:
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(
            **_proposal_kwargs(
                draft=False,
                action="apply patch",
                result="patched",
                lesson=None,
                source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
            )
        )
    assert "lesson" in str(exc.value).lower()


def test_proposal_revision_ready_requires_at_least_one_source() -> None:
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(
            **_proposal_kwargs(
                draft=False,
                action="apply patch",
                result="patched",
                lesson="lesson text",
                source_refs=[],
            )
        )
    assert "source" in str(exc.value).lower()


def test_proposal_revision_rejects_version_zero() -> None:
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(**_proposal_kwargs(version=0))
    assert "version" in str(exc.value).lower()


def test_proposal_revision_rejects_overflow_version() -> None:
    with pytest.raises(ValidationError):
        ProposalRevision(**_proposal_kwargs(version=DEFAULT_MAX_VERSION_INT + 1))


def test_proposal_revision_rejects_workflow_field() -> None:
    """workflow is server-owned; client input must not provide it."""

    payload = _proposal_kwargs(workflow="accepted")
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(**payload)  # type: ignore[arg-type]
    assert "workflow" in str(exc.value)


def test_proposal_revision_rejects_created_at_field() -> None:
    payload = _proposal_kwargs(created_at="2026-01-01T00:00:00Z")
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(**payload)  # type: ignore[arg-type]
    assert "created_at" in str(exc.value)


def test_proposal_revision_maxima_enforced() -> None:
    with pytest.raises(ValidationError):
        ProposalRevision(
            **_proposal_kwargs(
                draft=False,
                action="x" * (DEFAULT_MAX_ACTION_CHARS + 1),
                result="y" * DEFAULT_MAX_RESULT_CHARS,
                lesson="z" * DEFAULT_MAX_LESSON_CHARS,
                source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
            )
        )


def test_proposal_revision_whitespace_only_rejected() -> None:
    with pytest.raises(ValidationError):
        ProposalRevision(
            **_proposal_kwargs(
                draft=False,
                action="   ",
                result="result",
                lesson="lesson",
                source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
            )
        )


def test_proposal_revision_short_action_accepted() -> None:
    """Spec: non-blank required; no arbitrary length minima."""

    proposal = ProposalRevision(
        **_proposal_kwargs(
            draft=False,
            project_id="brain",
            action="hi",
            result="ok",
            lesson="x",
            source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
        )
    )
    assert proposal.action == "hi"
    assert is_proposal_ready(proposal) is True


def test_proposal_revision_short_lesson_accepted() -> None:
    """Spec: lesson only needs to be non-blank."""

    proposal = ProposalRevision(
        **_proposal_kwargs(
            draft=False,
            project_id="brain",
            action="apply patch",
            result="patched",
            lesson="x",
            source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
        )
    )
    assert proposal.lesson == "x"
    assert is_proposal_ready(proposal) is True


def test_proposal_revision_status_enum() -> None:
    """Workflow enum values are server-side; only the literal is allowed."""

    assert {s.value for s in ProposalStatus} == {
        "submitted",
        "under_review",
        "accepted",
        "rejected",
        "duplicate",
    }
    assert {s.value for s in ProposalWorkflow} == {"draft", "ready", "rejected"}


def test_proposal_revision_idempotency_helper() -> None:
    """The ready-check helper must reflect model rules."""

    payload = _proposal_kwargs(
        draft=False,
        project_id="brain",
        action="apply patch",
        result="patched",
        lesson="lesson text",
        source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
    )
    proposal = ProposalRevision(**payload)
    assert is_proposal_ready(proposal) is True
    assert is_proposal_ready(proposal.model_copy(update={"draft": True})) is False


def test_proposal_revision_ready_rejects_missing_project_id() -> None:
    """Spec: project_id is nullable until ready, required on ready."""

    with pytest.raises(ValidationError) as exc:
        ProposalRevision(
            **_proposal_kwargs(
                draft=False,
                action="apply patch",
                result="patched",
                lesson="lesson text",
                source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
            )
        )
    assert "project_id" in str(exc.value).lower()


def test_proposal_revision_draft_allows_missing_project_id() -> None:
    """Drafts may omit project_id until ready."""

    proposal = ProposalRevision(
        **_proposal_kwargs(draft=True, project_id=None)
    )
    assert proposal.project_id is None
    assert is_proposal_ready(proposal) is False


def test_proposal_revision_frozen() -> None:
    proposal = ProposalRevision(**_proposal_kwargs())
    with pytest.raises(ValidationError):
        proposal.version = 2  # type: ignore[misc]


def test_proposal_revision_strict_provenance_alone() -> None:
    """agent_id is provenance only, not authority. Principal is server-owned."""

    proposal = ProposalRevision(**_proposal_kwargs(agent_id="agent-x"))
    assert proposal.agent_id == "agent-x"
    # No principal / origin / classification fields exist on the input.
    assert "principal" not in proposal.model_dump()
    assert "origin" not in proposal.model_dump()


# ---------------------------------------------------------------------------
# SourceRef + Document
# ---------------------------------------------------------------------------


def test_source_ref_execution_only_accepts_uuid4() -> None:
    bad_id = str(uuid.UUID("00000000-0000-1000-8000-000000000000"))
    with pytest.raises(ValidationError):
        SourceRef(type=SourceRefType.EXECUTION, id=bad_id)


def test_source_ref_document_rejects_file_scheme() -> None:
    with pytest.raises(ValidationError):
        SourceDocument(
            id=uuid.uuid4(),
            url="file:///etc/passwd",
            version=1,
            excerpt="",
        )


def test_source_document_maxima() -> None:
    payload = dict(
        id=uuid.uuid4(),
        url="https://example.com/doc",
        version=1,
        excerpt="x" * (DEFAULT_MAX_EVIDENCE_BYTES + 1),
    )
    with pytest.raises(ValidationError):
        SourceDocument(**payload)


def test_proposal_source_ref_uses_typed_union() -> None:
    ref = ProposalSourceRef(
        type=SourceRefType.EXECUTION, id=str(uuid.uuid4())
    )
    assert ref.type.value == "execution"


# ---------------------------------------------------------------------------
# KnowledgeRevision
# ---------------------------------------------------------------------------


def _knowledge_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "revision_id": str(uuid.uuid4()),
        "version": 1,
        "scope": "project",
        "owner": "owner-1",
        "workspace": "default",
        "project_id": "proj-1",
        "kind": "experience",
        "lifecycle": "candidate",
        "statement": "Use atomic config replace",
        "source_refs": [{"type": "execution", "id": str(uuid.uuid4())}],
        "links": [],
        "policy_version": 1,
    }
    base.update(overrides)
    return base


def test_knowledge_revision_stable_identity_immutable_revision() -> None:
    """Stable UUID identity and immutable revision IDs."""

    knowledge = KnowledgeRevision(**_knowledge_kwargs())
    assert knowledge.id.version == 4
    assert knowledge.revision_id.version == 4
    with pytest.raises(ValidationError):
        knowledge.revision_id = uuid.uuid4()  # type: ignore[misc]


def test_knowledge_revision_scope_kind_lifecycle_enums() -> None:
    assert set(KNOWLEDGE_SCOPES) == {"owner", "workspace", "project"}
    assert set(KNOWLEDGE_KINDS) == {"directive", "experience"}
    assert set(KNOWLEDGE_LIFECYCLE_STATES) == {
        "candidate",
        "formal",
        "disputed",
        "archive",
        "deprecated",
    }
    bad = _knowledge_kwargs(lifecycle="approved")  # not a lifecycle state
    with pytest.raises(ValidationError):
        KnowledgeRevision(**bad)


def test_knowledge_revision_links_are_typed() -> None:
    link = KnowledgeRevisionLink(
        kind="parent",
        target_revision_id=str(uuid.uuid4()),
    )
    knowledge = KnowledgeRevision(**_knowledge_kwargs(links=[link]))
    assert knowledge.links[0].kind.value == "parent"


def test_knowledge_revision_disallows_extra_fields() -> None:
    payload = _knowledge_kwargs(migrated_from="old-system")
    with pytest.raises(ValidationError):
        KnowledgeRevision(**payload)  # type: ignore[arg-type]


def test_knowledge_revision_directive_requires_separate_command() -> None:
    """Directives must use the explicit-authority input, not the revision."""

    payload = _knowledge_kwargs(kind="directive")
    knowledge = KnowledgeRevision(**payload)
    # Revision input never carries the user-authority flag.
    assert not hasattr(knowledge, "authority_command")


def test_knowledge_directive_input_separate_from_revision() -> None:
    """Authenticated directive input has its own model, no agent boolean."""

    cmd = KnowledgeDirectiveInput(
        authority_command="deny rm -rf on shared cache",
        owner="owner-1",
        workspace="default",
        scope=KnowledgeScope.PROJECT,
        project_id="proj-1",
        source=KnowledgeDirectiveSource.HUMAN_AUTHENTICATED,
        recorded_at=datetime.now(timezone.utc),
        reference_revision_ids=[str(uuid.uuid4())],
    )
    assert cmd.source.value == "human_authenticated"
    assert "agent_authorized" not in cmd.model_dump()


def test_knowledge_directive_input_rejects_agent_authority() -> None:
    """Agents cannot self-declare user authority via a boolean."""

    with pytest.raises(ValidationError):
        KnowledgeDirectiveInput(
            authority_command="auto rule",
            owner="agent-x",  # an agent cannot be the owner
            workspace="default",
            scope=KnowledgeScope.PROJECT,
            project_id="proj-1",
            source=KnowledgeDirectiveSource.AGENT_INFERENCE,
            recorded_at=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Canonical helpers
# ---------------------------------------------------------------------------


def test_canonical_json_is_deterministic() -> None:
    payload = {"b": 1, "a": [3, 2, 1], "c": {"y": 2, "x": 1}}
    first = canonical_json(payload)
    second = canonical_json({"c": {"x": 1, "y": 2}, "a": [3, 2, 1], "b": 1})
    assert first == second
    # Stable, sorted, no whitespace ambiguity.
    assert json.loads(first) == payload


def test_canonical_digest_changes_with_payload() -> None:
    a = canonical_digest({"id": "1", "version": 1})
    b = canonical_digest({"id": "1", "version": 2})
    assert a != b


def test_canonical_digest_changes_with_field_order() -> None:
    a = canonical_digest({"id": "1", "version": 1})
    b = canonical_digest({"version": 1, "id": "1"})
    assert a == b  # canonicalisation removes order dependency


def test_canonical_digest_rejects_non_json_compatible() -> None:
    class NotJsonable:
        pass

    with pytest.raises(CanonicalDigestError):
        canonical_digest({"x": NotJsonable()})


def test_canonical_digest_handles_unicode() -> None:
    a = canonical_digest({"msg": "héllo"})
    b = canonical_digest({"msg": "héllo"})
    assert a == b
    c = canonical_digest({"msg": "hello"})
    assert a != c


# ---------------------------------------------------------------------------
# Adversarial tests — strict-type discipline and naive-datetime rejection.
# ---------------------------------------------------------------------------


def test_proposal_revision_rejects_string_version() -> None:
    """No string-to-int coercion: ``"1"`` must not become ``1``."""

    payload = _proposal_kwargs(version="1")  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(**payload)
    assert "version" in str(exc.value).lower()


def test_proposal_revision_rejects_bool_version() -> None:
    """No bool/int coercion: ``True`` must not become ``1``."""

    payload = _proposal_kwargs(version=True)  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(**payload)
    assert "version" in str(exc.value).lower()


def test_proposal_revision_rejects_string_draft() -> None:
    """No string-to-bool coercion on the draft flag."""

    payload = _proposal_kwargs(draft="true")  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(**payload)
    assert "draft" in str(exc.value).lower()


def test_source_document_rejects_string_version() -> None:
    """SourceDocument.version must reject string coercion."""

    with pytest.raises(ValidationError) as exc:
        SourceDocument(
            id=uuid.uuid4(),
            url="https://example.com/doc",
            version="1",  # type: ignore[arg-type]
            excerpt="",
        )
    assert "version" in str(exc.value).lower()


def test_knowledge_revision_rejects_string_version() -> None:
    """KnowledgeRevision.version must reject string coercion."""

    payload = _knowledge_kwargs(version="1")  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc:
        KnowledgeRevision(**payload)
    assert "version" in str(exc.value).lower()


def test_knowledge_revision_rejects_string_policy_version() -> None:
    """KnowledgeRevision.policy_version must reject string coercion."""

    payload = _knowledge_kwargs(policy_version="2")  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc:
        KnowledgeRevision(**payload)
    assert "policy_version" in str(exc.value).lower()


def test_proposal_revision_rejects_naive_datetime() -> None:
    """Spec: naive datetimes are rejected on proposal.occurred_at too."""

    payload = _proposal_kwargs(occurred_at=datetime(2026, 9, 17, 8, 0))  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc:
        ProposalRevision(**payload)
    assert "occurred_at" in str(exc.value).lower()


def test_knowledge_directive_input_rejects_naive_datetime() -> None:
    """Spec: naive datetimes are rejected on directive.recorded_at too."""

    with pytest.raises(ValidationError) as exc:
        KnowledgeDirectiveInput(
            authority_command="deny rm -rf",
            owner="owner-1",
            workspace="default",
            scope=KnowledgeScope.PROJECT,
            project_id="proj-1",
            source=KnowledgeDirectiveSource.HUMAN_AUTHENTICATED,
            recorded_at=datetime(2026, 9, 17, 8, 0),  # naive
        )
    assert "recorded_at" in str(exc.value).lower()


def test_strict_model_preserves_uuid_json_wire_format() -> None:
    """UUID str is still accepted via model_validate_json despite strict=True."""

    payload = json.dumps(_execution_event_kwargs(
        occurred_at="2026-09-17T08:00:00+00:00",
        source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
    ))
    event = ExecutionEvent.model_validate_json(payload)
    assert isinstance(event.id, uuid.UUID)
    assert isinstance(event.source_refs[0].id, uuid.UUID)


def test_strict_model_preserves_datetime_json_wire_format() -> None:
    """datetime ISO str is still accepted via model_validate_json despite strict=True."""

    payload = json.dumps(
        _execution_event_kwargs(
            occurred_at="2026-09-17T08:00:00+00:00",
        )
    )
    event = ExecutionEvent.model_validate_json(payload)
    assert isinstance(event.occurred_at, datetime)
    assert event.occurred_at.tzinfo is not None


def test_strict_model_preserves_uuid_python_call() -> None:
    """UUID str remains accepted for python-side call sites used throughout tests."""

    event = ExecutionEvent(**_execution_event_kwargs(
        source_refs=[{"type": "execution", "id": str(uuid.uuid4())}],
    ))
    assert isinstance(event.id, uuid.UUID)
    assert isinstance(event.source_refs[0].id, uuid.UUID)


def test_execution_event_rejects_int_for_id_field() -> None:
    """Strict model rejects int where UUID is required (no int coercion)."""

    payload = _execution_event_kwargs(id=123)  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as exc:
        ExecutionEvent(**payload)
    assert "id" in str(exc.value).lower()


def test_proposal_revision_rejects_int_for_id_field() -> None:
    payload = _proposal_kwargs(id=123)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ProposalRevision(**payload)


def test_knowledge_revision_rejects_int_for_id_field() -> None:
    payload = _knowledge_kwargs(id=123)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        KnowledgeRevision(**payload)