"""Local scoped retrieval with visibly separated authority lanes.

No archive fallback, promotion credit, cloud calls or permission grants.
"""
import re

def retrieve(store,principal,query,*,candidate_limit=3,limit=10,directives=None):
    if not isinstance(query,str) or not query.strip() or len(query)>2000:
        raise ValueError('bounded nonblank query required')
    if type(candidate_limit) is not int or not 0<=candidate_limit<=20:
        raise ValueError('invalid candidate cap')
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError('invalid retrieval limit')
    terms=set(re.findall(r'\w+',query.casefold()))
    result={'directives':directives.list_active(principal) if directives is not None else [],'formal':[],'candidates':[]}
    ranked=[]
    for row in store.list_current(principal):
        state=row['state']
        if state not in ('candidate','formal'): continue
        if row['kind']=='directive':
            # Authorization/owner-wide directive support must be supplied by
            # the dedicated directive store, never inferred from experience.
            continue
        words=set(re.findall(r'\w+',row['content'].casefold()))
        score=len(terms & words)
        if score: ranked.append((score,row))
    ranked.sort(key=lambda pair:(-pair[0],pair[1]['id']))
    for score,row in ranked:
        lane='formal' if row['state']=='formal' else 'candidates'
        cap=limit if lane=='formal' else candidate_limit
        if len(result[lane])<cap:
            result[lane].append({**row,'unverified':lane=='candidates','relevance':score})
    return result
