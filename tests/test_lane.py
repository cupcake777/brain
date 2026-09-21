from hermes.lane import assign_lane, canonical, classify, slug


def test_aliases_map_old_domains_but_keep_custom_slugs() -> None:
    assert canonical("devops") == "tech"
    assert canonical("STUDY") == "science"
    assert canonical("writing") == "writing"
    assert canonical("Teaching Notes") == "teaching-notes"
    assert slug("  ") == ""


def test_unlabeled_falls_back_to_text() -> None:
    assert assign_lane(
        hinted="global",
        text="When using salloc on the cu partition, request an explicit reservation.",
    ) == "science"
    assert assign_lane(
        hinted="general",
        project_key="global",
        text="nginx systemd unit failed after certbot renew on the VPS.",
    ) == "tech"


def test_custom_scene_is_not_overwritten() -> None:
    assert assign_lane(hinted="writing", text="salloc slurm hpc gene") == "writing"


def test_relabel_keeps_custom_and_maps_legacy(tmp_path) -> None:
    from hermes.repository import HermesRepository, KnowledgeNode

    repo = HermesRepository(tmp_path / "hermes.sqlite3")
    repo.insert_proposal({
        "proposal_id": "p-legacy",
        "source_agent": "test",
        "source_host": "ci",
        "created_at": "2026-09-01T00:00:00+00:00",
        "project_key": "global",
        "category": "rule",
        "risk_level": "low",
        "domain": "devops",
        "summary": "nginx restart after certbot",
        "observation": "VPS nginx unit failed",
        "why_it_matters": "ops",
        "suggested_memory": "Reload nginx after certbot renew.",
        "scope": "global",
        "evidence": "[]",
        "state": "pending",
        "semantic_hash": "h1",
        "inserted_at": "2026-09-01T00:00:00+00:00",
    })
    repo.insert_knowledge_node(KnowledgeNode(
        id="n-write",
        parent_id=None,
        content="Keep weekly notes short.",
        summary="Weekly notes stay short",
        category="preference",
        domain="writing",
        stage="canonized",
        operation="draft",
        confidence=0.8,
        source="test",
        evidence="[]",
        supersedes=None,
        merged_from="[]",
        contradicts="[]",
        verified_by="[]",
        created_at="2026-09-01T00:00:00+00:00",
        refined_at=None,
        verified_at=None,
        deprecated_at=None,
        retrieval_count=0,
        last_used_at=None,
        correction_count=0,
        outcome_count=0,
        last_outcome_at=None,
        kind="preference",
        trigger_terms="[]",
        use_when="",
        avoid_when="",
        success_signal="",
        failure_signal="",
    ))
    result = repo.relabel_lanes(dry_run=False)
    assert repo.get_proposal("p-legacy")["domain"] == "tech"
    assert repo.get_knowledge_node("n-write").domain == "writing"
    assert result["proposals_updated"] == 1
    assert result["knowledge_updated"] == 0


def test_classify_pending_style_notes() -> None:
    assert classify("On this HPC host, use the lowercase cu Slurm partition") == "science"
    assert classify("clusterProfiler::enricher() custom TERM2GENE") == "science"
    assert classify("For a corrupted SQLite store, preserve a consistent snapshot") == "tech"
    assert classify("install-skill-from-github.py SSLCertVerificationError") == "tech"
