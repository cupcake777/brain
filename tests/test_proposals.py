from pathlib import Path
from uuid import UUID

from hermes.proposals import ProposalWriter, load_front_matter


def test_proposal_writer_uses_atomic_temp_then_rename(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox" / "proposals"
    writer = ProposalWriter(inbox)

    proposal_path = writer.write(
        source_agent="codex",
        source_host="macbook",
        project_key="brain",
        category="rule",
        risk_level="high",
        summary="Prefer VPS-hosted Hermes as the single DB writer.",
        observation="The DB should never be synced via Syncthing.",
        why_it_matters="File sync is not a database replication protocol.",
        suggested_memory="Hermes is the only DB writer; clients sync text only.",
        scope="global",
        evidence="Observed repeated conflicts when syncing stateful DB files.",
    )

    assert proposal_path.parent == inbox
    assert proposal_path.exists()
    assert not list(inbox.glob(".tmp-*.md"))

    proposal_id = proposal_path.stem
    UUID(proposal_id)
    front_matter, body = load_front_matter(proposal_path)
    assert front_matter["proposal_id"] == proposal_id
    assert front_matter["status"] == "submitted"
    assert "Suggested durable memory" in body

