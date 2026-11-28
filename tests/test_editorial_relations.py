from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient
from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.editorial_relations import EditorialRelations
from hermes.environment_scope import assign
from hermes.integrate import integrate
from hermes.repository import HermesRepository
from tests.test_pipeline import _proposal


@pytest.fixture
def workspace(tmp_path,monkeypatch):
    monkeypatch.setenv('BRAIN_PROFILE_PATH',str(tmp_path/'profile.json'))
    monkeypatch.setenv('HERMES_ENV_FILE',str(tmp_path/'private.env'))
    repo=HermesRepository(tmp_path/'db')
    repo.insert_proposal(_proposal('a',state='pending',summary='Inspect scheduler failures'))
    repo.insert_proposal(_proposal('b',state='pending',summary='Check logs before resubmission'))
    repo.insert_proposal(_proposal('c',state='pending',summary='Unreviewed new item'))
    node=integrate(content='Read scheduler logs before repeating expensive jobs.',source='test',category='rule',domain='tech',evidence=['test://logs'],repo=repo)
    relations=EditorialRelations(repo)
    relations.add_topic('scheduler','调度与重跑','先看日志，再判断是否需要重跑。')
    config=HermesConfig(sync_root=tmp_path/'sync',db_path=repo.db_path)
    return repo,relations,TestClient(create_app(repo=repo,sync_root=config.sync_root,config=config)),node.node_id


def link(relations,repo,*,source='a',target='b',kind='proposal',relation='duplicate_of',**overrides):
    item=repo.get_proposal(target) if kind=='proposal' else asdict(repo.get_knowledge_node(target))
    args=dict(source_digest=relations.notes.digest('proposal',repo.get_proposal(source)),
              target_digest=relations.notes.digest(kind,item),reasoning='两条都要求重跑前查看调度日志，但第二条包含更多操作背景。',
              evidence=[{'source_uri':'test://comparison','quoted_excerpt':'Check logs before resubmission'}],
              reviewer='Codex',session_id='real-test-session')
    args.update(overrides)
    return relations.link('proposal',source,kind,target,relation,**args)


def test_typed_links_are_bidirectional_idempotent_and_do_not_approve(workspace):
    repo,relations,client,node_id=workspace
    edge_id=link(relations,repo)
    assert link(relations,repo)==edge_id
    link(relations,repo,target=node_id,kind='knowledge',relation='related_to')
    snapshot=relations.snapshot()
    assert len(snapshot['edges'])==2
    assert snapshot['by_entity'][('proposal','a')][0]['label']=='建议并入'
    assert snapshot['by_entity'][('proposal','b')][0]['label']=='待并入此条'
    for kind,identity in [('proposal','a'),('proposal','b'),('knowledge',node_id)]:
        url=f'/review/{identity}' if kind=='proposal' else f'/knowledge/{identity}'
        page=client.get(url).text
        assert '与其他记录的关系' in page
        assert '两条都要求' in page
        assert 'real-test-session' not in page  # Session attribution is stored, not scattered through UI.
    assert '/review/a' in client.get('/review/b').text
    assert f'/knowledge/{node_id}' in client.get('/review/a').text
    assert '/review/a' in client.get(f'/knowledge/{node_id}').text
    assert repo.get_proposal('a')['state']==repo.get_proposal('b')['state']=='pending'


def test_topic_membership_does_not_invent_semantic_links(workspace):
    repo,relations,client,_=workspace
    for identity in ('a','b'):
        item=repo.get_proposal(identity)
        relations.assign('scheduler','proposal',identity,expected_digest=relations.notes.digest('proposal',item),reviewer='Codex',session_id='test')
    snapshot=relations.snapshot()
    assert len(snapshot['edges'])==0
    page=client.get('/proposals').text
    assert 'data-topic="scheduler"' in page
    assert 'data-topic="unclassified"' in page
    assert '合并关系' not in page
    selected=client.get('/proposals?topic=scheduler').text
    assert '/review/a' in selected and '/review/b' in selected
    assert '/review/c' not in selected
    assert 'data-topic="scheduler" open' in selected


def test_any_endpoint_content_or_scope_change_invalidates_relation(workspace):
    repo,relations,client,_=workspace
    link(relations,repo)
    item=repo.get_proposal('b');old=relations.notes.digest('proposal',item)
    with repo._connect() as conn:
        conn.execute("UPDATE proposals SET suggested_memory='Different advice' WHERE proposal_id='b'")
    assert relations.snapshot()['edges']==[]
    assert relations.snapshot()['stale']==1
    assert '/review/b' not in client.get('/review/a').text
    with pytest.raises(ValueError,match='content changed'):
        link(relations,repo,target_digest=old)
    link(relations,repo)
    with repo._connect() as conn:assign(conn,'proposal','a',{'server_id':'other-host','user_root':'/home/b'})
    assert relations.snapshot()['edges']==[]


def test_symmetric_edges_normalize_and_missing_evidence_is_rejected(workspace):
    repo,relations,_,_=workspace
    first=link(relations,repo,relation='conflicts_with')
    second=link(relations,repo,source='b',target='a',relation='conflicts_with')
    assert first==second
    with pytest.raises(ValueError,match='invalid relation'):link(relations,repo,target='a')
    with pytest.raises(ValueError,match='evidence'):link(relations,repo,evidence=[])
    with pytest.raises(ValueError,match='identity'):link(relations,repo,reviewer='')


def test_relation_evidence_and_topic_titles_are_escaped(workspace):
    repo,relations,client,_=workspace
    payload='<img src=x onerror=alert(1)>'
    link(relations,repo,reasoning=payload,evidence=[{'source_uri':'test://x','quoted_excerpt':payload}])
    relations.add_topic('unsafe',payload,payload)
    item=repo.get_proposal('a')
    relations.assign('unsafe','proposal','a',expected_digest=relations.notes.digest('proposal',item),reviewer='Codex',session_id='test')
    for url in ('/proposals','/review/a'):
        html=client.get(url).text
        assert payload not in html
        assert '&lt;img src=x' in html


def test_all_sidebar_destinations_share_navigation_and_active_state(workspace):
    _,_,client,_=workspace
    pages=[('/','home'),('/knowledge','knowledge'),('/proposals','proposals'),('/projects','projects'),
           ('/environments','environments'),('/gallery','gallery'),('/settings','settings')]
    for url,key in pages:
        response=client.get(url)
        assert response.status_code==200
        html=response.text
        assert html.count('aria-label="主导航"')==1
        assert 'id="brainSidebar"' not in html and 'class="main-wrap"' not in html
        assert f'<a href="{url}" class="active" aria-current=page>' in html
        assert html.count('<main ')==1
    for url in ('/review/a?view=raw','/proposals?tab=flow','/knowledge?view=graph','/gallery/missing'):
        html=client.get(url).text
        assert 'aria-label="主导航"' in html
        assert 'id="brainSidebar"' not in html


def test_environment_proposal_links_open_compatibility_detail(workspace):
    repo,_,client,_=workspace
    with repo._connect() as conn:assign(conn,'proposal','a',{'server_id':'cluster','user_root':'/home/user'})
    html=client.get('/environments?q=cluster').text
    assert 'href="/review/a"' in html
    assert 'href="/proposals/a"' not in html
    assert client.get('/review/a').status_code==200


def test_settings_saves_profile_and_keeps_error_response_in_workspace(workspace,tmp_path):
    _,_,client,_=workspace
    response=client.post('/api/settings/profile',data={'display_name':'测试用户','theme':'modern-dark','lang':'zh'})
    assert response.status_code==200
    assert client.get('/api/settings/profile').json()['display_name']=='测试用户'
    html=client.get('/settings').text
    assert 'value="测试用户"' in html
    assert 'id="workspace-profile"' in html
    assert 'aria-label="主导航"' in html


def test_relationship_listing_is_owner_only(tmp_path):
    repo=HermesRepository(tmp_path/'db')
    config=HermesConfig(sync_root=tmp_path/'sync',db_path=repo.db_path,auth_token='secret')
    client=TestClient(create_app(repo=repo,sync_root=config.sync_root,config=config))
    assert client.get('/api/workspace/relationships').status_code==401
    assert client.get('/api/workspace/relationships',headers={'Authorization':'Bearer secret'}).status_code==200


@pytest.mark.parametrize('agent_token', [None, 'agent-token'])
def test_settings_password_keeps_browser_session_and_agent_token(tmp_path, monkeypatch, agent_token):
    monkeypatch.setenv('BRAIN_PROFILE_PATH', str(tmp_path/'profile.json'))
    env_file = tmp_path/'private.env'
    monkeypatch.setenv('HERMES_ENV_FILE', str(env_file))
    env_file.write_text('HERMES_PASSWORD=old-password\nHERMES_AUTH_TOKEN=agent-token\n')
    repo = HermesRepository(tmp_path/'db')
    config = HermesConfig(sync_root=tmp_path/'sync', db_path=repo.db_path,
                          auth_username='owner', auth_password='old-password', auth_token=agent_token)
    client = TestClient(create_app(repo=repo, sync_root=config.sync_root, config=config))
    origin = {'Origin': 'http://testserver'}
    assert client.post('/login', data={'username': 'owner', 'password': 'old-password'}, headers=origin, follow_redirects=False).status_code in {302,303}
    failed = client.post('/settings/password', data={'current_password': 'wrong'}, headers=origin)
    assert failed.status_code == 400 and '主导航' in failed.text
    assert '当前密码不正确' in failed.text
    changed = client.post('/settings/password', data={'current_password': 'old-password', 'new_password': 'new-password', 'confirm_password': 'new-password'}, headers=origin)
    assert changed.status_code == 200 and '密码已更新' in changed.text
    assert client.get('/settings', follow_redirects=False).status_code == 200
    assert client.get('/api/settings/profile').status_code == 200
    assert config.auth_token == agent_token
    assert 'HERMES_PASSWORD=new-password' in env_file.read_text()
    assert 'HERMES_AUTH_TOKEN=agent-token' in env_file.read_text()
    if agent_token:
        fresh = TestClient(client.app)
        assert fresh.get('/api/workspace/relationships', headers={'Authorization': 'Bearer '+agent_token}).status_code == 200


def test_token_only_settings_do_not_offer_browser_password_rotation(tmp_path, monkeypatch):
    monkeypatch.setenv('BRAIN_PROFILE_PATH', str(tmp_path/'profile.json'))
    repo = HermesRepository(tmp_path/'db')
    config = HermesConfig(sync_root=tmp_path/'sync', db_path=repo.db_path, auth_token='agent-token')
    client = TestClient(create_app(repo=repo, sync_root=config.sync_root, config=config))
    headers = {'Authorization': 'Bearer agent-token'}
    page = client.get('/settings', headers=headers)
    assert page.status_code == 200
    assert '当前使用访问令牌登录，令牌由服务配置管理。' in page.text
    assert 'action="/settings/password"' not in page.text
    assert client.post('/settings/password', data={'current_password':'agent-token','new_password':'replacement','confirm_password':'replacement'}, headers=headers).status_code == 400
    assert config.auth_token == 'agent-token'


def test_reviewed_relation_can_be_withdrawn_without_erasing_evidence(workspace):
    repo, relations, _, _ = workspace
    identity = link(relations, repo, relation='duplicate_of')
    relations.retire(identity, reasoning='Recomparison found complementary claims rather than equivalence.',
                     reviewer='independent-reviewer', session_id='actual-test-session')
    relations.retire(identity, reasoning='Repeated request', reviewer='independent-reviewer', session_id='actual-test-session')
    snapshot = relations.snapshot()
    assert snapshot['edges'] == [] and snapshot['stale'] == 0
    with repo._connect() as conn:
        assert conn.execute('SELECT count(*) FROM editorial_relationships WHERE id=?', (identity,)).fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM editorial_relationship_retirements WHERE relation_id=?', (identity,)).fetchone()[0] == 1
    with pytest.raises(ValueError, match='no longer exists'):
        relations.retire('missing', reasoning='Checked', reviewer='independent-reviewer', session_id='actual-test-session')
