from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
from hermes.knowledge_policy import DirectiveStore
from hermes.knowledge_retrieval_v2 import retrieve
from hermes.knowledge_archive import ArchiveSearch

def test_directives_are_constraints_even_when_query_does_not_match(tmp_path):
    p=Principal('human','w','p'); path=tmp_path/'db'
    store=KnowledgeStore(path)
    directives=DirectiveStore(path,authorize=lambda p:True)
    directive=directives.issue(p,'Never replay original side effects')
    result=retrieve(store,p,'unrelated search',directives=directives)
    assert result['directives'][0]['id']==directive['id']
    archive=ArchiveSearch(store,directives=directives)
    assert archive.normal_search(p,'unrelated search')['archive_ticket'] is None
    directives.close(); store.close()
