from copy import deepcopy
import json

import pytest

from hermes.editorial_relations import EditorialRelations
from hermes.environment_scope import assign
from hermes.proposal_curation import ProposalCuration
from hermes.repository import HermesRepository


def setup(tmp_path, count=2):
    repo = HermesRepository(tmp_path / 'brain.sqlite3')
    for i in range(count):
        repo.insert_proposal(dict(proposal_id=f'p{i}', source_agent='submitter', source_host='test',
            created_at='2026-11-28T00:00:00+00:00', project_key='brain', category='workflow_hint',
            risk_level='low', summary=f'Rule {i}', observation='Observed output', why_it_matters='Recurring behavior',
            suggested_memory=f'Check actual outputs for task {i}.', scope='global',
            evidence='source: test://result\nexcerpt: observed output', state='pending', semantic_hash=f'hash{i}'))
    curator = ProposalCuration(repo)
    plan = curator.prepare(reviewer='independent-reviewer', session_id='actual-test-session')
    for decision in plan['decisions']:
        decision.update(action='retain_db', reason='Specific output is evidenced by submission.',
            evidence_assessment='Submitted source was read; historical task was not rerun.')
    return repo, curator, plan


def test_dry_run_atomic_apply_replay_and_original_evidence(tmp_path):
    repo, curator, plan = setup(tmp_path)
    original = [repo.get_proposal(f'p{i}') for i in range(2)]
    assert curator.apply(plan)['dry_run']
    assert repo.counts_by_state()['pending'] == 2
    result = curator.apply(plan, dry_run=False)
    assert result['knowledge_created'] == 2
    assert repo.counts_by_state()['approved_db_only'] == 2
    assert curator.apply(plan, dry_run=False)['replayed']
    for before in original:
        current = repo.get_proposal(before['proposal_id'])
        for field in ('suggested_memory', 'summary', 'evidence', 'source_agent'):
            assert current[field] == before[field]
        link = repo.get_proposal_knowledge_link(before['proposal_id'])
        node = repo.get_knowledge_node(link['knowledge_id'])
        assert json.loads(node.evidence)[0]['quoted_excerpt'] == before['evidence']
        assert node.stage == 'refined' and node.verified_by == '[]'
        assert node.verified_at is None
    changed = deepcopy(plan); changed['decisions'][0]['reason'] = 'Other reason'
    with pytest.raises(ValueError, match='reused'):
        curator.apply(changed, dry_run=False)


def test_stale_content_or_scope_aborts_entire_batch(tmp_path):
    repo, curator, plan = setup(tmp_path)
    with repo._connect() as conn:
        assign(conn, 'proposal', 'p1', dict(server_id='server-a', user_root='/home/u'))
    with pytest.raises(ValueError, match='scope changed'):
        curator.apply(plan, dry_run=False)
    assert repo.counts_by_state()['pending'] == 2
    assert repo.list_knowledge_nodes(limit=20) == []


def test_duplicate_has_exact_target_without_new_node(tmp_path):
    repo, curator, plan = setup(tmp_path)
    canonical, duplicate = plan['decisions']
    duplicate.update(action='supersede', related_proposal_id=canonical['proposal_id'],
        target_digest=canonical['expected_digest'])
    result = curator.apply(plan, dry_run=False)
    assert result['knowledge_created'] == 1
    assert repo.get_proposal(duplicate['proposal_id'])['state'] == 'superseded'
    assert repo.get_proposal_knowledge_link(duplicate['proposal_id'])['knowledge_id'] == repo.get_proposal_knowledge_link(canonical['proposal_id'])['knowledge_id']
    assert len(EditorialRelations(repo).snapshot()['edges']) == 2


def test_archive_and_scoped_refinement_are_retained_honestly(tmp_path):
    repo, curator, plan = setup(tmp_path)
    first, second = plan['decisions']
    first.update(action='refine', proposed_memory='Only for the specified server, inspect output.',
        environment=dict(server_id='server-a', user_root='/home/u'))
    second.update(action='archive', reason='Obsolete setting; current evidence does not establish applicability.')
    curator.apply(plan, dry_run=False)
    assert repo.get_proposal(second['proposal_id'])['state'] == 'rejected'
    link = repo.get_proposal_knowledge_link(first['proposal_id'])
    assert repo.get_knowledge_node(link['knowledge_id']).content == first['proposed_memory']
    with repo._connect() as conn:
        scope = conn.execute("SELECT server_id,user_root FROM brain_environment_scopes WHERE entity_type='knowledge' AND entity_id=?", (link['knowledge_id'],)).fetchone()
        assert tuple(scope) == ('server-a', '/home/u')
    assert repo.get_proposal(first['proposal_id'])['suggested_memory'] != first['proposed_memory']


def test_duplicate_chain_and_self_approval_rejected(tmp_path):
    repo, curator, plan = setup(tmp_path)
    a, b = plan['decisions']
    a.update(action='supersede', related_proposal_id=b['proposal_id'], target_digest=b['expected_digest'])
    b.update(action='archive')
    with pytest.raises(ValueError, match='retained'):
        curator.apply(plan, dry_run=False)
    plan['reviewer'] = 'submitter'
    with pytest.raises(ValueError, match='own submission'):
        curator.apply(plan, dry_run=False)


def test_reviewed_relationships_become_current_knowledge_relationships(tmp_path):
    repo, curator, plan = setup(tmp_path)
    a, b = plan['decisions']
    EditorialRelations(repo).link('proposal', a['proposal_id'], 'proposal', b['proposal_id'], 'related_to',
        source_digest=a['expected_digest'], target_digest=b['expected_digest'], reasoning='Different checks on the same output.',
        evidence=[{'source_uri': 'test://comparison', 'quoted_excerpt': 'two checks'}], reviewer='independent-reviewer', session_id=plan['session_id'])
    result = curator.apply(plan, dry_run=False)
    assert result['knowledge_relationships'] == 1
    snapshot = EditorialRelations(repo).snapshot()
    assert snapshot['stale'] == 0
    assert sum(e['source_type'] == e['target_type'] == 'knowledge' for e in snapshot['edges']) == 1


def test_refined_mapping_never_inherits_old_relation_in_later_batch(tmp_path):
    repo, curator, plan = setup(tmp_path)
    a, b = plan['decisions']
    a.update(action='refine', proposed_memory='Narrowed output rule for different circumstances.')
    EditorialRelations(repo).link('proposal', a['proposal_id'], 'proposal', b['proposal_id'], 'related_to',
        source_digest=a['expected_digest'], target_digest=b['expected_digest'], reasoning='Original text comparison.',
        evidence=[{'source_uri': 'test://comparison', 'quoted_excerpt': 'original checks'}], reviewer='independent-reviewer', session_id=plan['session_id'])
    assert curator.apply(plan, dry_run=False)['knowledge_relationships'] == 0
    with repo._connect() as conn:
        now = '2026-11-28T01:00:00+00:00'
        unrelated = dict(plan, plan_id='next-independent-batch', decisions=[])
        assert curator.project_relationships(conn, unrelated, now) == 0


def test_existing_canonical_proposal_binds_actual_knowledge_and_digest(tmp_path):
    repo, curator, plan = setup(tmp_path)
    canonical_plan = dict(plan, decisions=[plan['decisions'][0]])
    curator.apply(canonical_plan, dry_run=False)
    canonical_id = canonical_plan['decisions'][0]['proposal_id']
    second = curator.prepare(reviewer='another-independent-reviewer', session_id='second-test-session')
    d = second['decisions'][0]
    canonical = repo.get_proposal(canonical_id)
    d.update(action='supersede', reason='Verified duplicate of retained object.', evidence_assessment='Compared both stored records.',
        related_proposal_id=canonical_id, target_digest=curator.notes.digest('proposal', canonical))
    with pytest.raises(ValueError, match='canonical knowledge link'):
        curator.apply(second, dry_run=False)
    link = repo.get_proposal_knowledge_link(canonical_id)
    with repo._connect() as conn:
        node = dict(conn.execute('SELECT * FROM knowledge_nodes WHERE id=?', (link['knowledge_id'],)).fetchone())
    d.update(canonical_knowledge_id=link['knowledge_id'], canonical_knowledge_digest=curator.notes.digest('knowledge', node))
    repo.update_knowledge_node(link['knowledge_id'], stage='deprecated')
    with pytest.raises(ValueError, match='deprecated'):
        curator.apply(second, dry_run=False)
