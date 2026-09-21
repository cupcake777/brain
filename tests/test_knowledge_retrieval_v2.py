from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_retrieval_v2 import retrieve

def test_retrieval_excludes_drafts_and_other_projects(tmp_path):
    store=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p')
    draft=store.create(p,'draft lesson',[])
    candidate=store.create(p,'candidate lesson',[])
    store.create(Principal('a','w','other'),'other project',[])
    with store.conn:
        store.conn.execute('INSERT INTO brain_v2_knowledge_states VALUES(?,?,?)',(candidate['id'],1,'candidate'))
    result=retrieve(store,p,'lesson',candidate_limit=1)
    assert result['directives']==[] and result['formal']==[]
    assert [r['id'] for r in result['candidates']]==[candidate['id']]
    assert result['candidates'][0]['unverified'] is True
    store.close()
