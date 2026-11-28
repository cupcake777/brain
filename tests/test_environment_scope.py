from __future__ import annotations

import json
import pytest

from hermes.environment_scope import assign, context, get_scope, scope_matches, inventory, page
from hermes.exporter import ExportCompiler
from hermes.integrate import integrate
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_retrieval_v2 import retrieve
from hermes.event_store import Principal
from hermes.repository import HermesRepository
from hermes.proposals import ProposalWriter
from tests.test_brain_protocol import client_with_token


def add(repo, env, text='Execute account verification through the configured scheduler.'):
    result=integrate(content=text,source='test',category='rule',domain='tech',
                     evidence=['test://scope'],repo=repo,environment=env)
    repo.update_knowledge_node(result.node_id,stage='verified')
    return result.node_id


def test_same_server_different_accounts_projects_and_global_knowledge(tmp_path):
    repo=HermesRepository(tmp_path/'db')
    global_node=add(repo,None,'Inspect scheduler logs before verification.')
    local={'server_id':'compute','user_root':'/home/alice','project_root':'/home/alice/work'}
    mine=add(repo,local)
    other_user=add(repo,{**local,'user_root':'/home/bob','project_root':'/home/bob/work'})
    other_server=add(repo,{**local,'server_id':'vps'})
    assert len({mine,other_user,other_server})==3  # No cross-context dedup.
    def search(env):return {r['id'] for r in repo.search_knowledge_nodes('verification scheduler',environment=env)}
    assert search(local)=={global_node,mine}
    assert search({**local,'project_root':'/home/alice/work/sub'})=={global_node,mine}
    assert search({**local,'project_root':'/home/alice/work-other'})=={global_node}
    assert search(None)=={global_node}
    exported=ExportCompiler(repo=repo,sync_root=tmp_path).build_knowledge_export().read_text()
    assert 'Inspect scheduler logs' in exported
    assert 'Execute account verification' not in exported
    with repo._connect() as conn:
        assert get_scope(conn,'knowledge',mine)['user_root']=='/home/alice'


def test_scope_filters_before_candidate_limit_and_preserves_explicit_directives(tmp_path):
    repo=HermesRepository(tmp_path/'db')
    principal=Principal('agent','w','p');store=KnowledgeStore(repo.db_path)
    mine={'server_id':'hpc','user_root':'/home/a'}
    other={'server_id':'hpc','user_root':'/home/b'}
    rows=[]
    for env in [other,mine]:
        row=store.create(principal,'account verification scheduler',[])
        with store.conn:
            store.conn.execute("INSERT INTO brain_v2_knowledge_states VALUES(?,?,'formal')",(row['id'],row['version']))
            assign(store.conn,'knowledge',row['id'],env)
        rows.append(row['id'])
    assert [r['id'] for r in retrieve(store,principal,'account verification scheduler',limit=1,environment=mine)['formal']]==[rows[1]]
    assert retrieve(store,principal,'account verification scheduler')['formal']==[]
    store.close()


def test_http_context_and_escaped_owner_inventory(tmp_path):
    client,repo,_=client_with_token(tmp_path);headers={'Authorization':'Bearer test-token'}
    env={'server_id':'<hpc>','user_root':'/home/a'}
    mine=add(repo,env)
    body={'query':'account verification scheduler','session_id':'real','environment':env}
    result=client.post('/api/v1/brain/retrieve',headers=headers,json=body).json()
    assert result['results'][0]['node_id']==mine
    assert result['results'][0]['environment']['server_id']=='<hpc>'
    body['environment']={'user_root':'/home/a'}
    assert client.post('/api/v1/brain/retrieve',headers=headers,json=body).status_code==400
    assert client.get('/api/v1/brain/environments').status_code==401
    assert client.get('/api/v1/brain/environments',headers=headers).status_code==200


@pytest.mark.parametrize('value',[[],{'user_root':'/home/a'},{'server_id':'hpc','user_root':'relative'},
                                   {'server_id':'hpc','project_root':'/home/a/../b'}])
def test_invalid_environment_rejected(value):
    with pytest.raises(ValueError):context(value)


def test_proposal_origin_and_applicability_survive_ingest_and_export(tmp_path):
    from hermes.ingest import IngestionService
    repo=HermesRepository(tmp_path/'db')
    origin={'server_id':'laptop','user_root':'/Users/author','project_root':'/Users/author/work'}
    scope={'server_id':'cluster-a','user_root':'/home/scientist','project_root':'/home/scientist/project'}
    writer=ProposalWriter(tmp_path/'inbox'/'proposals')
    proposal=writer.write(source_agent='test',source_host='legacy-hash',project_key='science',
        category='preference',risk_level='low',summary='Use scheduler for project verification',
        observation='The test fixture verified a scheduler wrapper for this project.',
        why_it_matters='Avoid selecting the workflow for an unrelated account.',
        suggested_memory='Use scheduler wrapper for science verification in the specified account.',
        scope='project',evidence='[{"source_type":"test","source_uri":"test://verified","quoted_excerpt":"Verification passed."}]',
        environment=scope,origin_environment=origin)
    IngestionService(repo=repo,sync_root=tmp_path).ingest_path(proposal)
    link=repo.get_proposal_knowledge_link(proposal.stem)
    assert link
    with repo._connect() as conn:
        assert get_scope(conn,'proposal',proposal.stem)['server_id']=='cluster-a'
        assert get_scope(conn,'knowledge',link['knowledge_id'])['user_root']=='/home/scientist'
        report=inventory(conn)
    assert report['groups'][0]['server_id']=='laptop'
    assert report['groups'][0]['user_root']=='/Users/author'
    assert report['groups'][0]['proposals'][0]['server_id']=='cluster-a'
    assert not repo.list_exportable()


def test_assignment_rebuilds_global_export_and_rejects_scoped_operator(tmp_path):
    from fastapi.testclient import TestClient
    from tests.test_scoped_auth import _registry, _app
    app=_app(tmp_path,_registry(tmp_path/'tokens.json',permissions=['knowledge:read']))
    client=TestClient(app)
    repo=HermesRepository(tmp_path/'brain.sqlite3')
    mine=add(repo,None,'Unique verification scheduler rule for account A.')
    body={'entity_type':'knowledge','entity_id':mine,'environment':{'server_id':'cluster','user_root':'/home/a'}}
    assert client.post('/api/v1/brain/environments/assign',json=body,headers={'Authorization':'Bearer agent-token'}).status_code in (401,403)
    result=client.post('/api/v1/brain/environments/assign',json=body,headers={'Authorization':'Bearer admin-token'})
    assert result.status_code==200,result.text
    text=(tmp_path/'exports/global/KNOWLEDGE.md').read_text()
    assert 'Unique verification' not in text
    headers={'Authorization':'Bearer agent-token'}
    assert client.post('/api/v1/brain/environment-export',headers=headers,json={'environment':body['environment']}).json()['node_ids']==[mine]
    assert client.get('/api/v1/brain/metrics',headers=headers).status_code in (401,403)
    assert client.get('/skills/brain-loop/scripts/brain.py',headers=headers).status_code==200


def test_hpc_path_does_not_alias_distinct_servers():
    from hermes.environment_scope import infer_legacy_environment
    env,_=infer_legacy_environment('Run sbatch for /hpc/home/alice/project verification.','auto-ingest')
    assert env['server_id']=='__unresolved__'
    env,_=infer_legacy_environment('Run sbatch for /hpc/home/alice/project verification.','hpc-login01')
    assert env['server_id']=='hpc-login01'
    assert not scope_matches(env,{'server_id':'other-cluster','user_root':'/hpc/home/alice'})


def test_environment_inventory_escapes_untrusted_origin_and_summary(tmp_path):
    from tests.test_pipeline import _proposal
    from hermes.environment_scope import assign_origin
    repo=HermesRepository(tmp_path/'db')
    proposal=_proposal('test',state='pending',summary='<script>bad()</script>')
    repo.insert_proposal(proposal)
    with repo._connect() as conn:
        assign_origin(conn,'proposal','test',{'server_id':'<img src=x>','user_root':'/home/a'})
        rendered=page(inventory(conn))
    assert '<script>bad()</script>' not in rendered and '<img src=x>' not in rendered
    assert 'aria-label="主导航"' in rendered
    assert '&lt;script&gt;' in rendered
    with repo._connect() as conn:
        rendered_origin=page(inventory(conn), view='origin')
    assert '<img src=x>' not in rendered_origin and '&lt;img src=x&gt;' in rendered_origin


def test_windows_paths_and_posix_root_scope(tmp_path):
    env=context({'server_id':'desktop','user_root':r'C:\Users\Alice','project_root':r'C:\Users\Alice\Work'})
    assert env['user_root']=='c:/users/alice'
    assert scope_matches(env,{'server_id':'desktop','user_root':'C:/Users/Alice','project_root':'C:/Users/Alice/Work/sub'})
    repo=HermesRepository(tmp_path/'db')
    node=add(repo,{'server_id':'vps','project_root':'/'})
    result=repo.search_knowledge_nodes('verification scheduler',environment={'server_id':'vps','project_root':'/work'})
    assert [r['id'] for r in result]==[node]


def test_context_projection_rebuild_removes_newly_scoped_or_retired_claim(tmp_path,monkeypatch):
    from tests.test_pipeline import _proposal
    from hermes.runtime import sync_proposal_to_brain_context
    target=tmp_path/'context.md'
    monkeypatch.setenv('HERMES_CONTEXT_PATH',str(target))
    repo=HermesRepository(tmp_path/'db')
    proposal=_proposal('projection',state='approved_for_export')
    proposal['scope']='global'
    repo.insert_proposal(proposal)
    assert sync_proposal_to_brain_context(proposal,'projection',repo=repo)
    assert 'Durable guidance for projection.' in target.read_text()
    with repo._connect() as connection:assign(connection,'proposal','projection',{'server_id':'other'})
    assert sync_proposal_to_brain_context(proposal,'projection',repo=repo)
    assert 'Durable guidance for projection.' not in target.read_text()
    repo.transition_state('projection','approved_db_only')
    assert 'Durable guidance for projection.' not in ExportCompiler(repo=repo,sync_root=tmp_path).export_brain_context().read_text()


def test_legacy_profile_requires_evidence_and_respects_path_boundary():
    from scripts.organize_brain_environments import inferred_scope
    profiles=[{'server_id':'cluster','user_root':'/home/a',
               'path_prefixes':['/mnt/old-home/a'],'evidence':['test://hostname-and-directory']}]
    env,reason=inferred_scope('Use /mnt/old-home/a/project on HPC.','auto-ingest',profiles)
    assert env['server_id']=='cluster' and env['user_root']=='/home/a'
    assert reason=='verified-path-profile'
    env,_=inferred_scope('Use /mnt/old-home/another/project on HPC.','auto-ingest',profiles)
    assert env['server_id']=='__unresolved__'
    with pytest.raises(ValueError):inferred_scope('path','source',[{**profiles[0],'evidence':[]}])
    other={**profiles[0],'server_id':'other','path_prefixes':['/mnt/other']}
    env,reason=inferred_scope('/mnt/old-home/a/project and /mnt/other/project','source',[*profiles,other])
    assert env['server_id']=='__unresolved__' and reason=='ambiguous-path-profiles'


def test_proposal_duplicate_detection_is_local_to_applicability(tmp_path):
    from tests.test_pipeline import _proposal
    repo=HermesRepository(tmp_path/'db')
    repo.insert_proposal(_proposal('a',state='pending'))
    scope={'server_id':'server-a','user_root':'/home/a'}
    with repo._connect() as connection:assign(connection,'proposal','a',scope)
    assert repo.find_by_semantic_hash('hash-a',environment=scope)=='a'
    assert repo.find_by_semantic_hash('hash-a',environment={'server_id':'server-b','user_root':'/home/a'}) is None
    assert repo.find_by_semantic_hash('hash-a',environment={}) is None
