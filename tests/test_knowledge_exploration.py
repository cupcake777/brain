from dataclasses import asdict
from html.parser import HTMLParser
import json

import pytest
from fastapi.testclient import TestClient

from hermes.app import create_app
from hermes.config import HermesConfig
from hermes.editorial_relations import EditorialRelations
from hermes.environment_scope import assign
from hermes.knowledge_exploration import build_exploration
from hermes.repository import HermesRepository
from tests.test_knowledge_detail import _stored_node
from tests.test_pipeline import _proposal


@pytest.fixture
def exploration(tmp_path, monkeypatch):
    monkeypatch.setattr("hermes.app._start_bg_runtime_if_needed", lambda *args: None)
    repo = HermesRepository(tmp_path/'brain.sqlite3')
    repo.insert_knowledge_node(_stored_node('root', created_at='2026-11-27T23:30:00+08:00'))
    repo.insert_knowledge_node(_stored_node('older'))
    repo.insert_knowledge_node(_stored_node('newer', parent_id='root', supersedes='root'))
    repo.insert_proposal(_proposal('proposal', state='pending', summary='Check scope before scheduler submission'))
    relations = EditorialRelations(repo)
    relations.link('proposal', 'proposal', 'knowledge', 'root', 'refines',
        source_digest=relations.notes.digest('proposal',repo.get_proposal('proposal')),
        target_digest=relations.notes.digest('knowledge',asdict(repo.get_knowledge_node('root'))),
        reasoning='Only applies to one scheduler partition.', evidence=[{'source_uri':'fixture://comparison','quoted_excerpt':'partition'}],
        reviewer='Reviewer', session_id='fixture-session')
    config = HermesConfig(sync_root=tmp_path/'sync', db_path=repo.db_path)
    client = TestClient(create_app(repo=repo, sync_root=config.sync_root, config=config))
    return repo, relations, client


def data(exploration):
    repo, relations, _ = exploration
    return build_exploration(repo,relations.snapshot(),'root')


def test_neighborhood_contains_current_editorial_and_both_directions_of_lineage(exploration):
    repo, _, _ = exploration
    repo.update_knowledge_node('root',supersedes='older',contradicts='["older"]')
    result=data(exploration)
    assert {item['key'] for item in result['nodes']} == {'knowledge:root','knowledge:older','knowledge:newer','proposal:proposal'}
    assert any(edge['source']=='knowledge:newer' and edge['target']=='knowledge:root' and edge['relation']=='supersedes' for edge in result['edges'])
    assert any(edge['source']=='proposal:proposal' and edge['origin']=='editorial' and edge['relation']=='refines' for edge in result['edges'])
    assert any(edge['relation']=='contradicts' for edge in result['edges'])


def test_stale_editorial_edges_are_excluded_and_topic_membership_invents_none(exploration):
    repo, relations, _=exploration
    relations.add_topic('scheduler','调度','调度规则')
    for identity in ('root','older'):
        relations.assign('scheduler','knowledge',identity,
            expected_digest=relations.notes.digest('knowledge',asdict(repo.get_knowledge_node(identity))),reviewer='Reviewer',session_id='fixture-session')
    with repo._connect() as conn:
        conn.execute("UPDATE proposals SET suggested_memory='Different scope now' WHERE proposal_id='proposal'")
    result=data(exploration)
    assert not any(edge['origin']=='editorial' for edge in result['edges'])
    assert 'knowledge:older' not in {item['key'] for item in result['nodes']}
    assert 'proposal:proposal' not in {item['key'] for item in result['nodes']}


def test_timeline_preserves_traffic_verification_and_exact_node_membership(exploration):
    repo,_,_=exploration
    with repo._connect() as conn:
        for identity, ids, date, traffic in [('actual','["root"]','2026-11-27T16:00:00Z','task'),('similar','["root-extra"]','2026-11-28T01:00:00Z','probe'),('malformed','broken json','2026-11-28T01:00:00Z','unknown'),('scalar','"root"','2026-11-28T01:00:00Z','probe')]:
            conn.execute('INSERT INTO knowledge_retrieval_events(id,query,node_ids,created_at,traffic_kind,agent) VALUES(?,?,?,?,?,?)',
                (identity,'Inspect scheduler',ids,date,traffic,'codex'))
        conn.execute('''INSERT INTO outcome_log(id,retrieval_log_id,memory_id,used,helpfulness,task_success,user_validated,notes,verification_note,created_at)
            VALUES('outcome','actual','root',1,'helpful','success',NULL,'Used the scoped rule','fixture acceptance passed','2026-11-27T16:01:00Z')''')
    result=data(exploration)
    events={item['id']:item for item in result['timeline']}
    assert 'retrieval-actual' in events and 'retrieval-similar' not in events and 'retrieval-malformed' not in events and 'retrieval-scalar' not in events
    assert events['retrieval-actual']['traffic']=='任务流量'
    assert '不表示已采用' in events['retrieval-actual']['proof']
    assert events['outcome-outcome']['evidence']=='fixture acceptance passed'
    assert '任务报告成功' in events['outcome-outcome']['decision']
    assert '用户已确认' not in events['outcome-outcome']['decision']
    sequence=[item['id'] for item in result['timeline']]
    assert sequence.index('retrieval-actual') < sequence.index('lifecycle-created_at')  # UTC ordering, not lexical offsets.


def test_history_keeps_old_reviews_explicit_and_scopes_visible(exploration):
    repo,relations,_=exploration
    item=asdict(repo.get_knowledge_node('root'))
    relations.notes.record('knowledge',item,expected_digest=relations.notes.digest('knowledge',item),
        reviewer='Reviewer',session_id='fixture-session',title_zh='旧导读',summary_zh='旧摘要',disposition='retain',
        reasoning='Evidence from submitted text.',next_step='Review on changed scope.')
    with repo._connect() as conn:
        assign(conn,'knowledge','root',{'server_id':'fixture-host','project_root':'/work/project'})
    result=data(exploration)
    assert next(node for node in result['nodes'] if node['key']==result['root'])['scope']=='fixture-host / /work/project'
    historical=[item for item in result['timeline'] if item['category']=='review' and item.get('historical')]
    assert historical and historical[0]['title']=='历史内容初审'
    assert '旧导读' not in next(node for node in result['nodes'] if node['key']==result['root'])['title']


def test_empty_neighborhood_and_bounded_history_are_explicit(exploration):
    repo,relations,_=exploration
    repo.insert_knowledge_node(_stored_node('isolated',parent_id=None,refined_at=None))
    with repo._connect() as conn:
        for i in range(45):
            conn.execute('INSERT INTO knowledge_retrieval_events(id,query,node_ids,created_at) VALUES(?,?,?,?)',
                (f'retrieval-{i:02}','query','["isolated"]',f'2026-11-27T12:{i:02}:00Z'))
    result=build_exploration(repo,relations.snapshot(),'isolated')
    assert result['counts']['neighbors']==0 and result['edges']==[]
    assert result['history_limited'] is True
    assert len([item for item in result['timeline'] if item['category']=='use'])==40


def test_reading_detail_does_not_change_records_or_counts(exploration):
    repo,_,client=exploration
    tables=['knowledge_nodes','thought_chains','proposals','knowledge_retrieval_events','outcome_log','editorial_relationships']
    def snapshot():
        with repo._connect() as conn:
            return {table:[tuple(row) for row in conn.execute(f'SELECT * FROM {table} ORDER BY 1')] for table in tables}
    before=snapshot()
    page=client.get('/knowledge/root')
    assert page.status_code==200
    assert 'id="local-graph"' in page.text and 'id="evolution-history"' in page.text
    assert 'id="knowledge-content"' in page.text
    assert '/workspace-assets/knowledge-explorer.js' in page.text
    assert 'Reviewer' in page.text and 'fixture-session' not in page.text
    assert before==snapshot()
    assert client.get('/workspace-assets/knowledge-explorer.js').status_code==200
    assert client.get('/workspace-assets/knowledge-explorer.css').status_code==200
    assert client.get('/knowledge/root?view=raw').status_code==200


class PayloadParser(HTMLParser):
    def __init__(self):
        super().__init__();self.active=False;self.payload='';self.handlers=[]
    def handle_starttag(self,tag,attrs):
        props=dict(attrs)
        if tag=='script' and props.get('id')=='knowledge-exploration-data':self.active=True
        self.handlers.extend(key for key in props if key.startswith('on'))
    def handle_data(self,value):
        if self.active:self.payload+=value
    def handle_endtag(self,tag):
        if tag=='script':self.active=False


def test_untrusted_content_cannot_break_inline_json_or_inject_handlers(exploration):
    repo,_,client=exploration
    attack='</script><img src=x onerror="window.fixtureInjected=true">\u2028 & text'
    repo.update_knowledge_node('root',summary=attack,content=attack,evidence=json.dumps([attack]))
    page=client.get('/knowledge/root')
    parser=PayloadParser();parser.feed(page.text)
    result=json.loads(parser.payload)
    assert next(node for node in result['nodes'] if node['key']==result['root'])['title']==attack
    assert '<img src=x onerror=' not in page.text
    assert not parser.handlers


def test_protected_detail_and_assets_require_authentication(tmp_path):
    repo=HermesRepository(tmp_path/'db')
    repo.insert_knowledge_node(_stored_node('node'))
    config=HermesConfig(sync_root=tmp_path/'sync',db_path=repo.db_path,auth_token='fixture-token')
    client=TestClient(create_app(repo=repo,sync_root=config.sync_root,config=config))
    for path in ['/knowledge/node','/workspace-assets/knowledge-explorer.js','/workspace-assets/knowledge-explorer.css']:
        assert client.get(path,follow_redirects=False).status_code in {303,401}
        assert client.get(path,headers={'Authorization':'Bearer fixture-token'}).status_code==200
