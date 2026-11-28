"""Experience applicability; provenance and access control remain separate."""
from __future__ import annotations
import html
from pathlib import PurePosixPath, PureWindowsPath

SCHEMA = """CREATE TABLE IF NOT EXISTS brain_environment_scopes (
 entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
 server_id TEXT NOT NULL DEFAULT '', user_root TEXT NOT NULL DEFAULT '',
 project_root TEXT NOT NULL DEFAULT '', attribution TEXT NOT NULL DEFAULT 'explicit',
 PRIMARY KEY(entity_type,entity_id));
 CREATE INDEX IF NOT EXISTS idx_environment_scope
 ON brain_environment_scopes(server_id,user_root,project_root);
 CREATE TABLE IF NOT EXISTS brain_environment_origins (
 entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, server_id TEXT NOT NULL,
 user_root TEXT NOT NULL DEFAULT '', project_root TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(entity_type,entity_id));"""


def context(value=None):
    if value is None: value={}
    if not isinstance(value,dict): raise ValueError('environment must be an object')
    result={}
    for key in ('server_id','user_root','project_root'):
        item=value.get(key,'')
        if not isinstance(item,str) or len(item)>500 or any(ord(ch)<32 for ch in item):
            raise ValueError(f'invalid environment {key}')
        item=item.strip()
        if key!='server_id' and item:
            windows=PureWindowsPath(item)
            if windows.drive:
                if not windows.is_absolute() or '..' in windows.parts:
                    raise ValueError(f'environment {key} must be an absolute normalized path')
                item=windows.as_posix().casefold()
            else:
                if not item.startswith('/') or '..' in PurePosixPath(item).parts:
                    raise ValueError(f'environment {key} must be an absolute normalized path')
                item=str(PurePosixPath(item))
        result[key]=item
    if (result['user_root'] or result['project_root']) and not result['server_id']:
        raise ValueError('environment server_id is required with directory scope')
    return result


def scope_matches(scope,current=None):
    current=context(current)
    if not scope or not scope.get('server_id'): return True
    if scope['server_id']!=current['server_id']:return False
    if scope.get('user_root') and scope['user_root']!=current['user_root']:return False
    root=scope.get('project_root','')
    return not root or current['project_root']==root or current['project_root'].startswith(root.rstrip('/')+'/')


def eligibility_sql(alias='kn',environment=None):
    current=context(environment)
    clause=f"""NOT EXISTS (SELECT 1 FROM brain_environment_scopes s
 WHERE s.entity_type='knowledge' AND s.entity_id={alias}.id AND s.server_id<>'' AND NOT (
 s.server_id=? AND (s.user_root='' OR s.user_root=?) AND
 (s.project_root='' OR s.project_root=? OR substr(?,1,length(rtrim(s.project_root,'/'))+1)=rtrim(s.project_root,'/')||'/')))"""
    return clause,[current['server_id'],current['user_root'],current['project_root'],current['project_root']]


def get_scope(connection,entity_type,entity_id):
    row=connection.execute('SELECT server_id,user_root,project_root,attribution FROM brain_environment_scopes WHERE entity_type=? AND entity_id=?',
                           (entity_type,entity_id)).fetchone()
    return dict(row) if row else {'server_id':'','user_root':'','project_root':'','attribution':'global'}


def assign(connection,entity_type,entity_id,environment,attribution='explicit'):
    if entity_type not in ('knowledge','proposal'):raise ValueError('invalid scoped entity')
    value=context(environment)
    connection.execute('INSERT INTO brain_environment_scopes VALUES (?,?,?,?,?,?) '
      'ON CONFLICT(entity_type,entity_id) DO UPDATE SET server_id=excluded.server_id,user_root=excluded.user_root,project_root=excluded.project_root,attribution=excluded.attribution',
      (entity_type,entity_id,value['server_id'],value['user_root'],value['project_root'],attribution))


def global_ids(connection,entity_type,ids):
    restricted={r[0] for r in connection.execute("SELECT entity_id FROM brain_environment_scopes WHERE entity_type=? AND server_id<>''",(entity_type,))}
    return set(ids)-restricted


def assign_origin(connection,entity_type,entity_id,environment):
    if entity_type not in ('knowledge','proposal'):raise ValueError('invalid origin entity')
    value=context(environment)
    connection.execute('INSERT INTO brain_environment_origins VALUES (?,?,?,?,?) '
      'ON CONFLICT(entity_type,entity_id) DO UPDATE SET server_id=excluded.server_id,user_root=excluded.user_root,project_root=excluded.project_root',
      (entity_type,entity_id,value['server_id'],value['user_root'],value['project_root']))


def inventory(connection):
    rows=connection.execute("""SELECT p.proposal_id,p.summary,p.source_host,p.project_key,
 COALESCE(s.server_id,'') server_id,COALESCE(s.user_root,'') user_root,
 COALESCE(s.project_root,'') project_root,COALESCE(s.attribution,'global') attribution,
 COALESCE(o.server_id,p.source_host) origin_server,COALESCE(o.user_root,'') origin_user_root,
 COALESCE(o.project_root,'') origin_project_root
 FROM proposals p LEFT JOIN brain_environment_scopes s
 ON s.entity_type='proposal' AND s.entity_id=p.proposal_id
 LEFT JOIN brain_environment_origins o ON o.entity_type='proposal' AND o.entity_id=p.proposal_id
 ORDER BY origin_server,origin_user_root,p.project_key,p.created_at DESC""").fetchall()
    groups={}
    applicability={}
    for row in rows:
        row=dict(row)
        identity=(row['origin_server'] or 'unknown',row['origin_user_root'])
        group=groups.setdefault(identity,{'server_id':identity[0],'user_root':identity[1],
          'proposals':[],'projects':set(),'source_hosts':set()})
        group['proposals'].append(row);group['projects'].add(row['project_key']);group['source_hosts'].add(row['source_host'])
        key=(row['server_id'] or 'shared',row['user_root'])
        bucket=applicability.setdefault(key,{'server_id':key[0],'user_root':key[1],'proposals':[],'knowledge':[]})
        bucket['proposals'].append(row)
    for group in groups.values():
        group['projects']=sorted(group['projects']);group['source_hosts']=sorted(group['source_hosts'])
    knowledge=[dict(r) for r in connection.execute("""SELECT COALESCE(s.server_id,'') server_id,
 COALESCE(s.user_root,'') user_root,COUNT(*) count FROM knowledge_nodes n
 LEFT JOIN brain_environment_scopes s ON s.entity_type='knowledge' AND s.entity_id=n.id
 WHERE n.stage IN ('canonized','verified','refined') GROUP BY 1,2""")]
    for node in connection.execute("""SELECT n.id,n.summary,n.domain,COALESCE(s.server_id,'') server_id,
 COALESCE(s.user_root,'') user_root,COALESCE(s.project_root,'') project_root
 FROM knowledge_nodes n LEFT JOIN brain_environment_scopes s
 ON s.entity_type='knowledge' AND s.entity_id=n.id
 WHERE n.stage IN ('canonized','verified','refined') ORDER BY n.summary"""):
        node=dict(node);key=(node['server_id'] or 'shared',node['user_root'])
        bucket=applicability.setdefault(key,{'server_id':key[0],'user_root':key[1],'proposals':[],'knowledge':[]})
        bucket['knowledge'].append(node)
    return {'schema':1,'groups':list(groups.values()),'knowledge_groups':knowledge,
      'applicability_groups':list(applicability.values()),
      'semantics':'Groups show origin server/user; environment is applicability. Unresolved scopes are withheld from retrieval.'}


def infer_legacy_environment(text,source_host=''):
    """Use explicit host/path evidence only; don't guess private server identities."""
    import re
    lower=text.casefold()
    roots=re.findall(r'/(?:gpfs/hpc/home|hpc/home|home|Users)/[A-Za-z0-9_.-]+|/root(?=/|\b)',text)
    roots=sorted(set(roots))
    hpc=bool(re.search(r'\bhpc\b|login[- ]node|\bslurm\b|\bsbatch\b',lower))
    if hpc:
        # Neither an HPC path nor a scheduler name proves which cluster it is.
        actual='hpc-login01' if source_host=='hpc-login01' or 'hpc-login01' in text else '__unresolved__'
        return {'server_id':actual,'user_root':roots[0] if len(roots)==1 else '',
                'project_root':''},'legacy-host-and-path-evidence' if actual!='__unresolved__' else 'needs-environment-review'
    if 'on this machine' in lower or 'on this host' in lower or 'on this hpc' in lower or any(term in text for term in ('当前用户环境','当前机器','这台机器','本机','本HPC')) or roots:
        actual=source_host if source_host and source_host not in ('auto-ingest','auto-cron','brain-web') else '__unresolved__'
        return {'server_id':actual,'user_root':roots[0] if len(roots)==1 else '',
                'project_root':''},'legacy-source-evidence' if actual!='__unresolved__' else 'needs-environment-review'
    return None,None


def page(report, *, query="", view="scope"):
    from .workspace_environments import page as workspace_page
    return workspace_page(report, query=query, view=view)
