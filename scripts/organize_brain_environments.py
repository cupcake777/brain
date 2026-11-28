#!/usr/bin/env python3
"""Add evidence-based environment metadata; preserve original knowledge text.

Retirement is opt-in: --retire-manifest accepts a JSON object mapping exact node
IDs to nonempty review reasons, for example {"fixture-node": "Superseded rule"}.
Without a manifest no knowledge nodes are retired, including with --apply.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hermes.environment_scope import infer_legacy_environment,assign,get_scope,assign_origin,context
from hermes.repository import HermesRepository

def validate_retirements(value):
    """Validate the entire explicit decision list before opening the database."""
    if not isinstance(value, dict):
        raise ValueError('retirement manifest must be a JSON object of node IDs and reasons')
    for node_id, reason in value.items():
        if not isinstance(node_id, str) or not node_id.strip() or node_id != node_id.strip():
            raise ValueError('retirement node IDs must be nonempty strings without surrounding whitespace')
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError('each retirement requires a nonempty review reason')
    return dict(value)


def inferred_scope(text,source_host,profiles):
    environment,reason=infer_legacy_environment(text,source_host)
    matched=[]
    for profile in profiles:
        if not profile.get('evidence'):raise ValueError('environment profile requires evidence')
        for prefix in profile.get('path_prefixes',[]):
            import re
            if not isinstance(prefix,str) or not prefix.startswith('/'):raise ValueError('invalid profile path prefix')
            if re.search(re.escape(prefix)+r'(?=/|[^A-Za-z0-9_.-]|$)',text):
                matched.append(context({key:profile.get(key,'') for key in ('server_id','user_root')}));break
    unique={tuple(value.items()) for value in matched}
    if len(unique)==1:
        # A target path establishes applicability, never the submission origin.
        return matched[0],'verified-path-profile'
    if len(unique)>1:return context({'server_id':'__unresolved__'}),'ambiguous-path-profiles'
    return environment,reason


def organize(db,output,apply=False,profiles=None,*,retire_nodes=None):
    retire_nodes=validate_retirements({} if retire_nodes is None else retire_nodes)
    profiles=profiles or []
    source=sqlite3.connect(f'file:{db}?mode=ro',uri=True);source.row_factory=sqlite3.Row
    proposals=[dict(r) for r in source.execute('SELECT proposal_id,source_host,suggested_memory,scope FROM proposals')]
    pmap={r['proposal_id']:r for r in proposals}
    nodes=[dict(r) for r in source.execute("SELECT id,content,source,stage FROM knowledge_nodes WHERE stage IN ('canonized','verified','refined')")]
    links={r['knowledge_id']:r['proposal_id'] for r in source.execute('SELECT knowledge_id,proposal_id FROM proposal_knowledge_links')}
    changes=[]
    for p in proposals:
        env,reason=inferred_scope(p['suggested_memory'],p['source_host'],profiles)
        if env:changes.append(dict(entity_type='proposal',entity_id=p['proposal_id'],environment=env,attribution=reason))
    for n in nodes:
        p=pmap.get(links.get(n['id'],n['id']),{})
        source_host=p.get('source_host','')
        if not source_host and n['source'].startswith('proposal:'):
            prefix=n['source'].split(':',1)[1]
            matches=[p for p in proposals if p['proposal_id'].startswith(prefix)]
            if len(matches)==1:source_host=matches[0]['source_host']
        if not source_host and n['source'].startswith('migration:') and '@' in n['source']:
            source_host=n['source'].rsplit('@',1)[1]
        env,reason=inferred_scope(n['content'],source_host,profiles)
        if env:changes.append(dict(entity_type='knowledge',entity_id=n['id'],environment=env,attribution=reason))
    review_edges=[dict(r) for r in source.execute("SELECT * FROM memory_edges WHERE edge_type='related_to' AND evidence_id LIKE 'text=%'")]
    source.close()
    report={'schema':1,'applied':False,'scope_assignments':changes,
            'review_edges_reclassified':review_edges,'retire_exact_nodes':retire_nodes,'preserves_original_content':True,
            'profiles':profiles,'created_at':datetime.now(timezone.utc).isoformat()}
    if apply:
        os.environ['BRAIN_DISABLE_EMBEDDINGS']='1'
        repo=HermesRepository(db)
        with repo._connect() as connection:
            for proposal in proposals:
                if not connection.execute("SELECT 1 FROM brain_environment_origins WHERE entity_type='proposal' AND entity_id=?",(proposal['proposal_id'],)).fetchone():
                    # Old source_host is preserved verbatim; a mentioned path does not prove the submitter's home.
                    assign_origin(connection,'proposal',proposal['proposal_id'],{'server_id':proposal['source_host']})
            for change in changes:
                # Never overwrite an operator's explicit assignment.
                previous=get_scope(connection,change['entity_type'],change['entity_id'])
                if previous['attribution']=='explicit':continue
                assign(connection,change['entity_type'],change['entity_id'],change['environment'],change['attribution'])
        with repo._connect() as connection:
            for edge in review_edges:
                connection.execute("INSERT OR IGNORE INTO memory_edges VALUES (?,?,?,?,?)",(edge['from_id'],edge['to_id'],'review_candidate',edge['evidence_id'],edge['created_at']))
                connection.execute("DELETE FROM memory_edges WHERE from_id=? AND to_id=? AND edge_type='related_to' AND evidence_id=?",(edge['from_id'],edge['to_id'],edge['evidence_id']))
        for node_id,reason in retire_nodes.items():
            if repo.get_knowledge_node(node_id) is not None:
                repo.update_knowledge_node(node_id,stage='deprecated',deprecated_at=datetime.now(timezone.utc).isoformat())
                with repo._connect() as connection:
                    linked={r[0] for r in connection.execute('SELECT proposal_id FROM proposal_knowledge_links WHERE knowledge_id=?',(node_id,))}
                node=repo.get_knowledge_node(node_id)
                if node and node.source.startswith('proposal:'):
                    prefix=node.source.split(':',1)[1]
                    matched=[p['proposal_id'] for p in proposals if p['proposal_id'].startswith(prefix)]
                    if len(matched)==1:linked.add(matched[0])
                if repo.has_proposal(node_id):linked.add(node_id)
                if node:
                    for proposal in proposals:
                        memory=(proposal['suggested_memory'] or '').strip()
                        if memory and (node.content.strip()==memory or node.content.startswith(memory+'\n\nObservation:')):
                            linked.add(proposal['proposal_id'])
                for pid in linked:repo.retire_proposal_knowledge(pid,reason)
        report['applied']=True
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    by_server={}
    for change in changes:
        server=change['environment']['server_id'];by_server[server]=by_server.get(server,0)+1
    print(json.dumps({'applied':report['applied'],'assignments':len(changes),'by_server':by_server,'retire_ids':len(retire_nodes)},ensure_ascii=False))

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--profiles',type=Path)
    p.add_argument('--retire-manifest',type=Path,
                   help='JSON object mapping exact node IDs to review reasons; default: no retirements')
    p.add_argument('--apply',action='store_true');a=p.parse_args(argv)
    profiles=json.loads(a.profiles.read_text()).get('profiles',[]) if a.profiles else []
    retire_nodes=validate_retirements(json.loads(a.retire_manifest.read_text())) if a.retire_manifest else {}
    organize(a.db,a.output,a.apply,profiles,retire_nodes=retire_nodes)


if __name__=='__main__':
    main()
