"""Local scoped retrieval with visibly separated authority lanes.

No archive fallback, promotion credit, cloud calls or permission grants.
"""
from hermes.retrieval_lexical import query_terms, term_coverage, required_coverage

def retrieve(store,principal,query,*,candidate_limit=3,limit=10,directives=None,environment=None):
    if not isinstance(query,str) or not query.strip() or len(query)>2000:
        raise ValueError('bounded nonblank query required')
    if type(candidate_limit) is not int or not 0<=candidate_limit<=20:
        raise ValueError('invalid candidate cap')
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError('invalid retrieval limit')
    terms=query_terms(query)
    result={'directives':directives.list_active(principal) if directives is not None else [],'formal':[],'candidates':[]}
    if not terms: return result
    ranked=[]
    from hermes.environment_scope import get_scope, scope_matches
    for row in store.list_current(principal):
        if not scope_matches(get_scope(store.conn,'knowledge',row['id']),environment):continue
        state=row['state']
        if state not in ('candidate','formal'): continue
        if row['kind']=='directive':
            # Authorization/owner-wide directive support must be supplied by
            # the dedicated directive store, never inferred from experience.
            continue
        score=term_coverage(terms,row['content'])
        if score >= required_coverage(terms): ranked.append((score,row))
    ranked.sort(key=lambda pair:(-pair[0],pair[1]['id']))
    for score,row in ranked:
        lane='formal' if row['state']=='formal' else 'candidates'
        cap=limit if lane=='formal' else candidate_limit
        if len(result[lane])<cap:
            result[lane].append({**row,'unverified':lane=='candidates','relevance':score})
    return result
