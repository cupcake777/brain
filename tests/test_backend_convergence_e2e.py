from datetime import datetime, timezone
from uuid import uuid4

import pytest

from hermes.brain_events import ReferenceEvents
from hermes.checks import CheckLedger
from hermes.event_store import ConflictError, EventStore, Principal, StaticPrincipalAdapter, UnauthorizedError
from hermes.knowledge_archive import ArchiveSearch, InactivityPolicy
from hermes.knowledge_conflicts import ConflictCases
from hermes.knowledge_extraction import ExtractionQueue
from hermes.knowledge_policy import DirectiveStore, VerifiedUseLedger
from hermes.knowledge_promotion import PromotionPolicy
from hermes.knowledge_retrieval_v2 import retrieve
from hermes.knowledge_sources import RegisteredSources
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_workflow import KnowledgeWorkflow


def test_disposable_event_to_archive_and_directive_lifecycle(tmp_path):
    agent = Principal("agent-a", "workspace-a", "brain")
    human = Principal("human-a", "workspace-a", "brain")
    adapter = StaticPrincipalAdapter(
        actor=agent.actor,
        workspace=agent.workspace,
        project=agent.project,
    )
    events = EventStore(tmp_path / "events.sqlite3", principal=adapter)
    event_id = str(uuid4())
    event_receipt = events.record_event(
        id=event_id,
        project_id="brain",
        agent_id="agent-a",
        occurred_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
        action="verify disposable fixture",
        result="fixture passed",
    )
    assert event_receipt["id"] == event_id
    assert event_receipt["version"] == 1
    assert len(event_receipt["digest"]) == 64

    knowledge_path = tmp_path / "knowledge.sqlite3"
    knowledge = KnowledgeStore(knowledge_path)
    queue = ExtractionQueue(
        knowledge,
        event_reader=lambda principal, identity: events.get_event(identity),
    )
    queue.enqueue(agent, event_id)
    assert queue.run_once(
        agent,
        lambda event: [{"content": "verify archive fixture before reuse"}],
    )["state"] == "completed"
    item = knowledge.list_current(agent)[0]

    sources = RegisteredSources(events)
    source_versions = sources(agent, item["source_refs"])
    checks = CheckLedger(
        knowledge,
        required=("privacy", "source", "support"),
        policy_version="e2e-test-policy",
    )
    for name in checks.required:
        checks.record(
            agent,
            item["id"],
            1,
            name,
            "passed",
            item["digest"],
            source_versions,
        )
    workflow = KnowledgeWorkflow(knowledge, checks, source_resolver=sources)
    assert workflow.accept(agent, item["id"], 1)["state"] == "candidate"

    proof = {
        "verified": True,
        "classification": "production",
        "knowledge_id": item["id"],
        "version": 1,
        "task_id": "task-1",
        "execution_id": "execution-1",
    }
    uses = VerifiedUseLedger(knowledge, verifier=lambda principal, identity: proof)
    assert uses.record(agent, item["id"], 1, "task-1", "execution-1") is True
    policy = PromotionPolicy(
        knowledge,
        uses,
        threshold=1,
        readiness=lambda principal, identity, version: checks.ready(
            principal, identity, version, source_versions
        ),
    )
    assert policy.promote(agent, item["id"], 1) is True
    assert retrieve(knowledge, agent, "archive fixture")["formal"][0]["id"] == item["id"]

    revised = knowledge.revise(
        agent,
        item["id"],
        1,
        "verify archive fixture after evidence changes",
        item["source_refs"],
    )
    assert revised["version"] == 2
    assert checks.ready(agent, item["id"], 1, source_versions) is False
    assert retrieve(knowledge, agent, "archive fixture")["formal"] == []

    competitor = knowledge.create(
        agent,
        "archive fixture has a contradictory rule",
        item["source_refs"],
    )
    conflicts = ConflictCases(knowledge, authorize=lambda principal: principal.actor == "human-a")
    case_id = conflicts.open(agent, [item["id"], competitor["id"]])
    assert knowledge.get(agent, item["id"])["state"] == "disputed"
    with pytest.raises(UnauthorizedError):
        conflicts.resolve(agent, case_id)
    conflicts.resolve(human, case_id)
    assert knowledge.get(agent, item["id"])["state"] == "draft"

    archive_policy = InactivityPolicy(knowledge, cutoff_seconds=10, clock=lambda: 100)
    assert archive_policy.archive(agent, item["id"], 2, last_used_at=0) is True
    archive = ArchiveSearch(knowledge, clock=lambda: 100)
    normal = archive.normal_search(agent, "archive fixture")
    assert normal["formal"] == [] and normal["candidates"] == []
    archived = archive.search(agent, normal["archive_ticket"], explicit=True)
    assert archived[0]["id"] == item["id"]
    assert archived[0]["requires_revalidation"] is True

    directives = DirectiveStore(knowledge_path, authorize=lambda principal: principal.actor == "human-a")
    directive = directives.issue(human, "Never replay original side effects")
    separated = retrieve(knowledge, human, "unrelated query", directives=directives)
    assert separated["directives"][0]["id"] == directive["id"]
    assert separated["formal"] == []

    references = ReferenceEvents(knowledge)
    reference_id = references.emit(human, "completed", item["id"])
    assert references.emit(human, "completed", item["id"]) == reference_id
    assert references.deliver_once(human, lambda payload: {"delivered": 1})["state"] == "delivered"

    directives.close()
    knowledge.close()
    events.close()
