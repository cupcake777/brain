from pathlib import Path

from hermes.exporter import ExportCompiler
from hermes.ingest import IngestionService
from hermes.proposals import ProposalWriter
from hermes.repository import HermesRepository
from hermes.status import StatusPublisher


def _write_proposal(
    writer: ProposalWriter,
    *,
    source_agent: str,
    source_host: str,
    project_key: str,
    category: str,
    risk_level: str,
    suggested_memory: str,
    observation: str = "Observed behavior.",
) -> Path:
    return writer.write(
        source_agent=source_agent,
        source_host=source_host,
        project_key=project_key,
        category=category,
        risk_level=risk_level,
        summary=suggested_memory,
        observation=observation,
        why_it_matters="Because it affects durable behavior.",
        suggested_memory=suggested_memory,
        scope="project",
        evidence="Local test evidence.",
    )


def test_ingestion_routes_low_risk_preference_to_db_only(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    writer = ProposalWriter(tmp_path / "sync" / "inbox" / "proposals")
    service = IngestionService(repo=repo, sync_root=tmp_path / "sync")

    path = _write_proposal(
        writer,
        source_agent="claude",
        source_host="macbook",
        project_key="brain",
        category="preference",
        risk_level="low",
        suggested_memory="Prefer concise status exports over raw proposal history.",
    )

    outcome = service.ingest_path(path)
    stored = repo.get_proposal(outcome.proposal_id)

    assert outcome.route == "approved_db_only"
    assert stored["state"] == "approved_db_only"
    assert stored["semantic_duplicate_of"] is None


def test_ingestion_keeps_semantic_duplicates_as_merge_candidates(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    writer = ProposalWriter(tmp_path / "sync" / "inbox" / "proposals")
    service = IngestionService(repo=repo, sync_root=tmp_path / "sync")

    first = _write_proposal(
        writer,
        source_agent="claude",
        source_host="macbook",
        project_key="brain",
        category="rule",
        risk_level="high",
        suggested_memory="Use atomic rename for proposal publication.",
        observation="Syncthing can expose partial files.",
    )
    second = _write_proposal(
        writer,
        source_agent="codex",
        source_host="windows",
        project_key="brain",
        category="rule",
        risk_level="high",
        suggested_memory="Use atomic rename for proposal publication.",
        observation="Syncthing can expose partial files.",
    )

    first_outcome = service.ingest_path(first)
    second_outcome = service.ingest_path(second)

    assert first_outcome.route == "pending"
    duplicate = repo.get_proposal(second_outcome.proposal_id)
    assert duplicate["state"] == "pending"
    assert duplicate["semantic_duplicate_of"] == first_outcome.proposal_id


def test_export_compiler_builds_budgeted_project_snapshot(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    writer = ProposalWriter(tmp_path / "sync" / "inbox" / "proposals")
    ingest = IngestionService(repo=repo, sync_root=tmp_path / "sync")
    compiler = ExportCompiler(repo=repo, sync_root=tmp_path / "sync")

    first_path = _write_proposal(
        writer,
        source_agent="claude",
        source_host="macbook",
        project_key="brain",
        category="rule",
        risk_level="high",
        suggested_memory="Old rule that should be superseded.",
    )
    second_path = _write_proposal(
        writer,
        source_agent="codex",
        source_host="macbook",
        project_key="brain",
        category="rule",
        risk_level="high",
        suggested_memory="New rule that replaces the old one.",
    )

    first_id = ingest.ingest_path(first_path).proposal_id
    second_id = ingest.ingest_path(second_path).proposal_id
    repo.transition_state(first_id, "approved_for_export")
    repo.transition_state(second_id, "approved_for_export", supersedes=first_id)

    export_path = compiler.build_project_export("brain")
    content = export_path.read_text(encoding="utf-8")

    assert "New rule that replaces the old one." in content
    assert "Old rule that should be superseded." not in content
    assert export_path.stat().st_size <= compiler.budgets.project_hard_cap


def test_status_publisher_writes_status_markdown(tmp_path: Path) -> None:
    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    writer = ProposalWriter(tmp_path / "sync" / "inbox" / "proposals")
    ingest = IngestionService(repo=repo, sync_root=tmp_path / "sync")
    compiler = ExportCompiler(repo=repo, sync_root=tmp_path / "sync")
    status = StatusPublisher(repo=repo, sync_root=tmp_path / "sync")

    proposal = _write_proposal(
        writer,
        source_agent="claude",
        source_host="macbook",
        project_key="brain",
        category="rule",
        risk_level="high",
        suggested_memory="Publish state/status.md at least hourly.",
    )
    proposal_id = ingest.ingest_path(proposal).proposal_id
    repo.transition_state(proposal_id, "approved_for_export")
    compiler.build_project_export("brain")

    status_path = status.publish()
    content = status_path.read_text(encoding="utf-8")

    assert content.startswith("# Hermes Status")
    assert "approved_for_export: 1" in content
    assert "brain.md: last rebuilt" in content

