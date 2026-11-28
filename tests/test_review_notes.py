from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.environment_scope import assign
from hermes.integrate import integrate
from hermes.repository import HermesRepository
from hermes.review_notes import ReviewNotes


@pytest.fixture
def setup_workspace(tmp_path):
    repo = HermesRepository(tmp_path / 'db.sqlite3')
    proposal = dict(proposal_id='p1', source_agent='submitter', source_host='local',
                    created_at='2026-07-24T00:00:00Z', project_key='test', category='workflow_hint',
                    risk_level='low', summary='Keep scheduler logs', observation='Observed logs',
                    why_it_matters='Recover failed jobs', suggested_memory='Read logs before rerun',
                    scope='project', evidence='source: test://job\nexcerpt: failed',
                    state='pending', semantic_hash='0' * 64)
    repo.insert_proposal(proposal)
    node_id = integrate(content='Inspect scheduler logs before a costly rerun.',
                        source='test', category='rule', domain='tech', evidence=['test://job'], repo=repo).node_id
    config = HermesConfig(sync_root=tmp_path/'sync', db_path=repo.db_path)
    return repo, ReviewNotes(repo), TestClient(create_app(repo=repo, sync_root=config.sync_root, config=config)), node_id


def record(notes, item, kind='proposal', **overrides):
    fields = dict(reviewer='Codex', session_id='review-session', title_zh='任务重跑前看调度日志',
                  summary_zh='查看失败日志，确定是否需要重跑。', disposition='retain',
                  reasoning='有明确触发情境和可执行步骤。', next_step='在下一次任务中验证。',
                  expected_digest=notes.digest(kind, item))
    fields.update(overrides)
    return notes.record(kind, item, **fields)


def test_review_is_attributed_and_never_approves_content(setup_workspace):
    repo, notes, client, _ = setup_workspace
    record(notes, repo.get_proposal('p1'))
    summary = client.get('/api/workspace/reviews').json()
    assert summary['reviewed'] == summary['pending'] == 1
    review = summary['items'][0]['review']
    assert review['reviewer'] == 'Codex'
    assert review['session_id'] == 'review-session'
    assert review['evidence_check'] == 'submitted_text_only'
    assert repo.get_proposal('p1')['state'] == 'pending'
    page = client.get('/review/p1').text
    assert '任务重跑前看调度日志' in page
    assert '内容初审者' in page and 'submitter' in page
    assert '未重新执行历史任务' in page
    assert '有明确触发情境' in page


def test_changes_invalidate_review_and_reject_stale_writer(setup_workspace):
    repo, notes, client, _ = setup_workspace
    item = repo.get_proposal('p1')
    record(notes, item)
    with repo._connect() as conn:
        conn.execute("UPDATE proposals SET suggested_memory='New recommendation' WHERE proposal_id='p1'")
    with pytest.raises(ValueError, match='content changed'):
        record(notes, item)
    summary = client.get('/api/workspace/reviews').json()
    assert summary['reviewed'] == 0
    assert summary['items'][0]['review_outdated']
    page = client.get('/review/p1').text
    assert '内容已变' in page
    assert '任务重跑前看调度日志' not in page
    # Old attribution remains available for audit, with no stale badge on the new content.
    assert len(notes.all('proposal')) == 1


def test_scope_changes_invalidate_notes(setup_workspace):
    repo, notes, _, _ = setup_workspace
    item = repo.get_proposal('p1')
    record(notes, item)
    with repo._connect() as conn:
        assign(conn, 'proposal', 'p1', {'server_id': 'new-server', 'user_root': '/home/other'})
    attached = notes.attach('proposal', [item])[0]
    assert attached['editorial_review'] is None and attached['review_outdated']
    with pytest.raises(ValueError, match='content changed'):
        record(notes, item, expected_digest=notes.all('proposal')['p1']['content_digest'])


def test_deleted_target_and_missing_identity_rejected(setup_workspace):
    repo, notes, _, _ = setup_workspace
    item = repo.get_proposal('p1')
    with pytest.raises(ValueError, match='required'):
        record(notes, item, reviewer=' ')
    with repo._connect() as conn:
        conn.execute("DELETE FROM proposals WHERE proposal_id='p1'")
    with pytest.raises(ValueError, match='no longer exists'):
        record(notes, item)


def test_chinese_search_and_pending_filters_use_current_review(setup_workspace):
    repo, notes, client, node_id = setup_workspace
    record(notes, repo.get_proposal('p1'), disposition='merge')
    assert '/review/p1' in client.get('/proposals?q=调度&bucket=merge').text
    assert '/review/p1' not in client.get('/proposals?bucket=unreviewed').text
    assert '/review/p1' not in client.get('/proposals?bucket=conflict').text
    record(notes, asdict(repo.get_knowledge_node(node_id)), 'knowledge')
    assert f'/knowledge/{node_id}' in client.get('/knowledge?q=调度').text
    assert '中文导读' in client.get(f'/knowledge/{node_id}').text
    repo.update_knowledge_node(node_id, stage='deprecated')
    assert f'/knowledge/{node_id}' not in client.get('/knowledge').text
    assert f'/knowledge/{node_id}' in client.get('/knowledge?stage=all').text


def test_review_markup_is_escaped_and_old_hint_is_not_a_current_relation(setup_workspace):
    repo, notes, client, _ = setup_workspace
    payload = '<img src=x onerror=alert(1)>'
    record(notes, repo.get_proposal('p1'), title_zh=payload, reasoning=payload,
           related_id='../" onmouseover="alert(1)')
    page = client.get('/review/p1').text
    assert payload not in page
    assert '&lt;img src=x' in page
    assert '/review/..%2F%22%20onmouseover%3D%22alert%281%29' not in page
    assert '尚未记录经过比较的重复、冲突或补充关系。' in page


def test_review_summary_requires_owner_auth(tmp_path):
    repo = HermesRepository(tmp_path/'db')
    config = HermesConfig(sync_root=tmp_path/'sync', db_path=repo.db_path, auth_token='owner-token')
    client = TestClient(create_app(repo=repo, sync_root=config.sync_root, config=config))
    assert client.get('/api/workspace/reviews').status_code == 401
    assert client.get('/api/workspace/reviews', headers={'Authorization': 'Bearer owner-token'}).status_code == 200
