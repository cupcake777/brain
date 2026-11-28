#!/usr/bin/env python3
"""Replay labelled fixtures in isolated, randomized model contexts.

The default 12 cases are tagged historical-deployment-20261127; their evidence
IDs refer to that deployment, not a portable benchmark. --fixture accepts JSON
{"label": "my-fixture", "cases": [{"id": "case", "group": "helpful",
"query": "lookup", "prompt": "Return result.txt", "evidence": "fixture://case",
"expected_files": {"result.txt": "expected text"}}]}. Exact-file checks never
execute fixture or model code. --fixture-label can override the source label.

For model calls supply --base-url, --model and --api-key-env/--api-key-file, or
explicit --config and --provider for the existing Hermes providers YAML format.
${NAME} credentials use process environment or an explicit --env-file. Nothing
reads a home-directory configuration or credential file implicitly. Equivalent
BRAIN_PILOT_CONFIG/PROVIDER/BASE_URL/MODEL/API_KEY/API_KEY_FILE/ENV_FILE environment
variables are supported. --prepare-only needs no provider or credentials.


Uses frozen existing knowledge and executable acceptance predicates. The replay
is diagnostic, not a claim about unobserved live users. No generated code runs;
model output consists only of text artifacts interpreted by the fixture judge.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import random
import re
import shlex
import sqlite3
import sys
import time
from urllib.parse import urlsplit
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HISTORICAL_FIXTURE_LABEL = 'historical-deployment-20261127'

CASES = [
    dict(id='xiaomi-routing', group='helpful', query='xiaomi auxiliary delegation api_key base_url 401',
         evidence='knowledge:13158590-f591-4bfb-abe3-4bd2bccc637f',
         prompt='Repair this Hermes Xiaomi provider configuration so auxiliary and delegation use the native PROVIDER_REGISTRY. Preserve other providers. Return config.json. Input: {"auxiliary":{"provider":"xiaomi","api_key":"fixture-key","base_url":"https://fixture.invalid/v1"},"delegation":{"provider":"xiaomi","api_key":"fixture-key","base_url":"https://fixture.invalid/v1"},"other":{"provider":"local","base_url":"http://127.0.0.1:9"}}'),
    dict(id='project-memory', group='helpful', query='project-local cross-session memory .mem .codex',
         evidence='knowledge:b1f2c8d7-7b8a-4d7d-a5d8-4d1d4a7c3e21',
         prompt='Create a persistent project memory artifact for resuming an interrupted task on this project host. Preserve this goal: repair ranking and verify the outcome. Pick the project marker/storage convention used on this host. Return that memory file.'),
    dict(id='hpc-python-verification', group='helpful', query='HPC login Python R verification Slurm scheduler',
         evidence='knowledge:155a9cff-aee6-4b1e-ba9a-aecdd970c619',
         prompt='On the HPC login node, prepare execution of a 10-second Python verification script verify.py. Return run.sh and verify.py. The script must print verified. Follow this host execution convention; prepare artifacts only.'),
    dict(id='stop-hook-timeout', group='helpful', query='Codex recap Stop hook timeout 5 eight seconds',
         evidence='knowledge:f6b99be0-c4c8-412b-aad3-e46fb703e200',
         prompt='Fix the Codex recap Stop hook configuration. It exits 0 when run alone in 8.2 seconds; timeout 5 returns 124. Current config: {"hook":"python3 recap.py","timeout":5}. Return config.json preserving the command and use the smallest whole-second timeout with at least 20 percent timing headroom.'),
    dict(id='workstation-python', group='trap', query='Python verification login Slurm HPC',
         evidence='feedback.md:scope-applicability',
         prompt='Target is a local Linux developer workstation, not HPC. There is no Slurm installation. Prepare run.sh to run verify.py directly with Python 3. The current user explicitly requires direct local execution. Return run.sh.'),
    dict(id='custom-provider', group='trap', query='xiaomi auxiliary api_key base_url provider registry',
         evidence='knowledge:13158590-f591-4bfb-abe3-4bd2bccc637f:out-of-scope',
         prompt='Target is a custom provider fixture named custom:lab, not native Xiaomi. Its contract requires api_key and base_url directly in the auxiliary entry. Preserve this valid config unchanged in config.json: {"auxiliary":{"provider":"custom:lab","api_key":"fixture-key","base_url":"https://fixture.invalid/v1"}}'),
    dict(id='explicit-memory-path', group='trap', query='project-local cross-session memory .mem .codex',
         evidence='knowledge:b1f2c8d7-7b8a-4d7d-a5d8-4d1d4a7c3e21:current-user-override',
         prompt='For this new fixture the current user explicitly chooses state/session.md as project memory. Create exactly that file containing resume goal: verify capture. Prior conventions for other projects must not change this explicit path.'),
    dict(id='current-approval-policy', group='trap', query='Brain low-risk facts automatic approval canonized two days',
         evidence='feedback.md:obsolete-auto-approval',
         prompt='Generate policy.json for the current Brain governance contract: low-risk preferences may be approved database-only. Facts and lifecycle promotion require human review. There is no elapsed-time auto-canonization. Fields: preferences_db_auto (boolean), facts_auto (boolean), lifecycle_auto (boolean), canonize_after_days (number or null).'),
    dict(id='utf8-json', group='no_knowledge', query='utf8_fixture_47 JSON parser newline accent',
         evidence='retrieval-lexical-evaluation.md:unicode-regression',
         prompt='Return config.json containing exactly {"label":"café 检索","enabled":true,"count":3}. Preserve Unicode spelling and JSON types.'),
    dict(id='binary-key', group='no_knowledge', query='backup binary key whitespace 32 bytes boundary',
         evidence='tests/test_brain_backup.py:whitespace-regression',
         prompt='A binary encryption key is exactly 32 raw bytes. Leading and trailing ASCII whitespace are valid key bytes. Return policy.json with fields expected_length, strip, decode_text, compare_raw_bytes representing the correct loader behavior.'),
    dict(id='empty-retrieval', group='no_knowledge', query='xyzzymissingprotocol_47 no knowledge result',
         evidence='tests/test_retrieval_lexical.py:no-answer',
         prompt='An experience lookup returned results=[], retrieval_id="", outcome_required=false. Return actions.json with keys create_feedback, fabricate_node, proceed_with_task (booleans). Continue the user task without inventing feedback.'),
    dict(id='result-metrics', group='no_knowledge', query='metrics_denominator_47 candidate outcomes requests',
         evidence='feedback.md:counts-not-success',
         prompt='An audit observes 4 retrieval requests, each returning 3 candidates; there are 12 candidate outcomes, all task_success=unknown and user_validated=null. Return metrics.json with retrieval_requests, candidate_outcomes, measured_task_success_rate (number or null). Do not infer task success from feedback count.'),
]


def judge(case, files):
    """Executable acceptance, receives artifacts only and never model arm."""
    if 'expected_files' in case:
        return files == case['expected_files']
    def load(name): return json.loads(files[name])
    cid = case['id']
    if cid == 'xiaomi-routing':
        config=load('config.json')
        return all(config[k]['provider']=='xiaomi' and not ({'api_key','base_url'} & config[k].keys()) for k in ('auxiliary','delegation')) and config['other']=={'provider':'local','base_url':'http://127.0.0.1:9'}
    if cid == 'project-memory':
        return any((p=='.mem' or p.startswith('.mem/')) and 'repair ranking' in text.casefold() and 'verify' in text.casefold() for p,text in files.items()) and not any(p=='.codex' or p.startswith('.codex/') for p in files)
    if cid == 'hpc-python-verification':
        commands=[line.strip() for line in files['run.sh'].splitlines() if line.strip() and not line.startswith('#')]
        scheduled=any('sbatch' in line or 'submit_job.sh' in line for line in commands) or ('#SBATCH' in files['run.sh'] and any(line.startswith('srun ') for line in commands))
        return scheduled and not any(line.startswith(('python','Rscript')) for line in commands) and 'verified' in files['verify.py']
    if cid == 'stop-hook-timeout': return load('config.json')=={'hook':'python3 recap.py','timeout':10}
    if cid == 'workstation-python': return 'python3' in files['run.sh'] and 'verify.py' in files['run.sh'] and 'sbatch' not in files['run.sh']
    if cid == 'custom-provider': return load('config.json')=={'auxiliary':{'provider':'custom:lab','api_key':'fixture-key','base_url':'https://fixture.invalid/v1'}}
    if cid == 'explicit-memory-path': return set(files)=={'state/session.md'} and 'verify capture' in files['state/session.md']
    if cid == 'current-approval-policy': return load('policy.json')=={'preferences_db_auto':True,'facts_auto':False,'lifecycle_auto':False,'canonize_after_days':None}
    if cid == 'utf8-json': return load('config.json')=={'label':'café 检索','enabled':True,'count':3}
    if cid == 'binary-key': return load('policy.json')=={'expected_length':32,'strip':False,'decode_text':False,'compare_raw_bytes':True}
    if cid == 'empty-retrieval': return load('actions.json')=={'create_feedback':False,'fabricate_node':False,'proceed_with_task':True}
    if cid == 'result-metrics': return load('metrics.json')=={'retrieval_requests':4,'candidate_outcomes':12,'measured_task_success_rate':None}
    raise ValueError('unknown task')


def _read_provider_file(path, description):
    try:
        return Path(path).expanduser().read_text()
    except (OSError, UnicodeError):
        raise RuntimeError('Invalid ' + description + ' file') from None


def _credential_environment(path):
    values = {}
    if path:
        for line in _read_provider_file(path, 'credential environment').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.fullmatch(r'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)', line)
            if not match:
                raise ValueError('Invalid credential environment assignment')
            try:
                parts = shlex.split(match[2], comments=True)
            except ValueError:
                raise ValueError('Invalid credential environment quoting') from None
            if len(parts) > 1:
                raise ValueError('Credential environment values containing spaces must be quoted')
            values[match[1]] = parts[0] if parts else ''
    return {**values, **os.environ}


def load_provider(config_path=None, provider_name=None, *, base_url=None, model=None,
                  api_key_env=None, api_key_file=None, env_file=None):
    """Resolve only explicit config; errors never include credential values.

    Precedence: explicit key file, explicit key environment name, default
    BRAIN_PILOT_API_KEY, then the selected provider's api_key (literal or ${NAME}).
    URL/model arguments override BRAIN_PILOT_* and provider configuration.
    """
    config_path = config_path or os.environ.get('BRAIN_PILOT_CONFIG')
    provider_name = provider_name or os.environ.get('BRAIN_PILOT_PROVIDER')
    if api_key_file is not None and api_key_env is not None:
        raise ValueError('Choose either a credential file or an environment variable')
    if api_key_file is None and api_key_env is None:
        api_key_file = os.environ.get('BRAIN_PILOT_API_KEY_FILE')
    env_file = env_file or os.environ.get('BRAIN_PILOT_ENV_FILE')
    provider = {}
    if config_path:
        import yaml
        try:
            config = yaml.safe_load(_read_provider_file(config_path, 'provider configuration'))
        except yaml.YAMLError:
            raise ValueError('Invalid provider configuration YAML') from None
        providers = config.get('providers') if isinstance(config, dict) else None
        if not provider_name or not isinstance(providers, dict) or provider_name not in providers:
            raise ValueError('Select an existing provider with --provider or BRAIN_PILOT_PROVIDER')
        provider = providers[provider_name]
        if not isinstance(provider, dict):
            raise ValueError('Selected provider must be a configuration object')
    elif provider_name:
        raise ValueError('Selecting a provider requires an explicit configuration file')
    origin = base_url or os.environ.get('BRAIN_PILOT_BASE_URL') or provider.get('base_url')
    model = model or os.environ.get('BRAIN_PILOT_MODEL') or provider.get('default_model')
    if (not isinstance(origin, str) or not isinstance(model, str) or not model.strip()
            or any(ord(char) < 32 for char in model)):
        raise ValueError('Set a model and base URL explicitly or in the selected provider')
    try:
        parsed = urlsplit(origin)
        valid_url = (parsed.scheme == 'https' or
                     parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1', '::1'))
        valid_url = (valid_url and parsed.hostname and parsed.username is None and parsed.password is None
                     and not parsed.query and not parsed.fragment and parsed.port != 0
                     and not any(char.isspace() or ord(char) < 32 for char in origin))
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError('Model base URL must use HTTPS or loopback HTTP without credentials, query or fragment')
    environment = _credential_environment(env_file)
    if api_key_file:
        key = _read_provider_file(api_key_file, 'model credential').strip()
    elif api_key_env is not None:
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', api_key_env):
            raise ValueError('Invalid credential environment variable name')
        key = environment.get(api_key_env, '')
    else:
        key = environment.get('BRAIN_PILOT_API_KEY') or provider.get('api_key', '')
        if isinstance(key, str) and key.startswith('${'):
            match = re.fullmatch(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', key)
            if not match:
                raise ValueError('Invalid provider credential environment reference')
            key = environment.get(match[1], '')
    if not isinstance(key, str) or not key.strip() or any(ord(char) < 32 for char in key.strip()):
        raise RuntimeError('Configured model credential is missing or invalid')
    return origin.rstrip('/'), key.strip(), model.strip()


def valid_files(files):
    return isinstance(files, dict) and bool(files) and all(
        isinstance(name, str) and bool(name) and isinstance(text, str)
        and not Path(name).is_absolute() and '..' not in Path(name).parts
        and not PureWindowsPath(name).drive and '..' not in PureWindowsPath(name).parts
        for name, text in files.items())


def load_fixture(fixture=None, fixture_label=None):
    """Load data-only cases; external cases may use exact-file expectations."""
    data = json.loads(Path(fixture).read_text()) if fixture else {
        'label': HISTORICAL_FIXTURE_LABEL, 'cases': [dict(case) for case in CASES]}
    if not isinstance(data, dict):
        raise ValueError('Fixture must be a JSON object with label and cases')
    label = fixture_label if fixture_label is not None else data.get('label')
    cases = data.get('cases')
    if not isinstance(label, str) or not label.strip() or any(ord(c) < 32 for c in label):
        raise ValueError('Fixture requires a nonempty source label')
    if not isinstance(cases, list) or not cases:
        raise ValueError('Fixture cases must be a nonempty list')
    seen = set()
    known_ids = {case['id'] for case in CASES}
    for case in cases:
        if not isinstance(case, dict) or not all(
                isinstance(case.get(key), str) and case[key].strip()
                for key in ('id', 'group', 'query', 'prompt')):
            raise ValueError('Each fixture case requires id, group, query and prompt strings')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', case['id']) or case['id'] in seen:
            raise ValueError('Fixture case IDs must be unique filename-safe identifiers')
        seen.add(case['id'])
        if 'expected_files' in case:
            if not valid_files(case['expected_files']):
                raise ValueError('Fixture expected_files must map relative file names to text')
        elif case['id'] not in known_ids:
            raise ValueError('Fixture cases require expected_files or a built-in validator ID')
    return label, cases


def prepare(snapshot, output, *, fixture=None, fixture_label=None):
    label, cases = load_fixture(fixture, fixture_label)
    output.mkdir(parents=True, exist_ok=True)
    os.environ['BRAIN_DISABLE_EMBEDDINGS']='1'
    from hermes.repository import HermesRepository
    # Work only on a second frozen copy; preserve the original snapshot.
    copied=output/'pilot.sqlite3'
    if not copied.exists():
        src=sqlite3.connect(f'file:{snapshot}?mode=ro',uri=True);dest=sqlite3.connect(copied)
        src.backup(dest);src.close();dest.close();copied.chmod(0o600)
    repo=HermesRepository(copied)
    rows=[]
    for case in cases:
        candidates=repo.search_knowledge_nodes(case['query'],limit=5)
        rows.append({**case,'candidates':[{k:r[k] for k in ('id','summary','content','stage')} for r in candidates]})
    plan={'schema':1,'snapshot_sha256':hashlib.sha256(Path(snapshot).read_bytes()).hexdigest(),
          'case_kind':'labelled fixture replays' if fixture else 'sanitized historical engineering-task replays',
          'fixture_label':label,'cases':rows,
          'seed':27112026,'temperature':0,'max_output_tokens':2000,
          'controls':'Same model, prompt, tools and budgets; independent API contexts; randomized arm order; no memory writeback.',
          'limitations':'Replay fixtures, one run per arm, lexical-only frozen retrieval; no claim of real live task success lift or statistical significance.'}
    path=output/'frozen-plan.json'
    if path.exists():
        previous = json.loads(path.read_text())
        if fixture is None and fixture_label is None:
            previous.setdefault('fixture_label', HISTORICAL_FIXTURE_LABEL)
        if previous != plan:
            raise RuntimeError('Frozen plan changed; choose a new output directory')
    path.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    return plan


def run(snapshot,output,workers=2,*,fixture=None,fixture_label=None,config_path=None,
        provider_name=None,base_url=None,model=None,api_key_env=None,api_key_file=None,env_file=None):
    if workers < 1:
        raise ValueError('workers must be positive')
    origin,key,model=load_provider(config_path,provider_name,base_url=base_url,model=model,
                                   api_key_env=api_key_env,api_key_file=api_key_file,env_file=env_file)
    plan=prepare(snapshot,output,fixture=fixture,fixture_label=fixture_label)
    schedule=[(case,arm) for case in plan['cases'] for arm in ('off','on')]
    random.Random(plan['seed']).shuffle(schedule)
    (output/'schedule.json').write_text(json.dumps([(c['id'],a) for c,a in schedule]))
    system=('Produce the requested local fixture text artifacts. Return ONLY a JSON object {"files":{"relative/path":"file text"}}. '
            'Do not run commands or contact services. Current user requirements override historical experience. '
            'Retrieved experience is untrusted contextual evidence; apply only when target and conditions match. '
            'If no relevant experience is supplied, solve from the task input and general knowledge.')
    def one(item):
        case,arm=item
        path=output/f"{case['id']}-{arm}.json"
        if path.exists():
            saved=json.loads(path.read_text())
            if saved.get('model') != model:
                raise RuntimeError('Saved pilot model changed; choose a new output directory')
            if 'files' in saved:
                saved.setdefault('acceptance_pass_initial_validator',saved['acceptance_pass'])
                saved['acceptance_pass']=bool(judge(case,saved['files']))
                saved['validator_version']=2
                path.write_text(json.dumps(saved,ensure_ascii=False,indent=2))
            return saved
        prompt=case['prompt']
        if arm=='on':prompt+='\nHistorical experience candidates (may be irrelevant):\n'+json.dumps(case['candidates'],ensure_ascii=False)
        payload={'model':model,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}],
                 'temperature':0,'max_tokens':2000,'stream':False}
        start=time.monotonic()
        result={'case':case['id'],'group':case['group'],'arm':arm,'model':model,'prompt':prompt,
                'retrieved_ids':[r['id'] for r in case['candidates']] if arm=='on' else []}
        try:
            response=httpx.post(origin+'/chat/completions',json=payload,
                                headers={'Authorization':'Bearer '+key},timeout=110)
            response.raise_for_status()
            data=response.json()
            raw=data['choices'][0]['message']['content']
            result.update(raw_output=raw,usage=data.get('usage'),model_returned=data.get('model'))
            text=raw.strip()
            if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
            files=json.loads(text)['files']
            if not valid_files(files):
                raise ValueError('Invalid text artifacts')
            result['files']=files
            result['acceptance_pass']=bool(judge(case,files))
        except Exception as exc:
            # Never print request headers or provider error response bodies.
            result.update(acceptance_pass=False,error_type=type(exc).__name__)
            if hasattr(exc, 'code'): result['http_status']=exc.code
        result['duration_seconds']=round(time.monotonic()-start,3)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps({k:result[k] for k in ('case','arm','acceptance_pass','duration_seconds')},ensure_ascii=False),flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        rows=list(pool.map(one,schedule))
    summary={}
    for arm in ('off','on'):
        runs=[r for r in rows if r['arm']==arm]
        usages=[r.get('usage') for r in runs]
        groups = sorted({case['group'] for case in plan['cases']})
        summary[arm]={'tasks':len(runs),'accepted':sum(r['acceptance_pass'] for r in runs),
                      'by_group':{g:sum(r['acceptance_pass'] for r in runs if r['group']==g) for g in groups},
                      'summed_request_seconds':round(sum(r['duration_seconds'] for r in runs),3),
                      'total_tokens':sum(u.get('total_tokens',0) for u in usages if u) if all(usages) else None,
                      'errors':sum('error_type' in r for r in runs)}
    result={'schema':1,'model_requested':model,'summary':summary,'runs':len(rows),
            'case_kind':plan['case_kind'],'fixture_label':plan['fixture_label'],'limitations':plan['limitations'],
            'validator_version':2,'validator_corrections':'Case-insensitive goal preservation and acceptance of existing submit_job.sh/srun scheduler workflows. Original verdicts retained per run.',
            'creates_production_events':False,'cost_usd':None,
            'interpretation':'Acceptance uses executable artifact predicates. Usage is provider-reported; price is not supplied. No live-user outcome was fabricated.'}
    (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False),flush=True)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--fixture',type=Path,help='Labelled data-only cases with exact expected_files')
    p.add_argument('--fixture-label',help='Explicit provenance label for the selected cases')
    p.add_argument('--config',dest='config_path',type=Path,help='Explicit Hermes provider YAML')
    p.add_argument('--provider',dest='provider_name',help='Provider entry in the explicit YAML')
    p.add_argument('--base-url',help='HTTPS API base URL, or loopback HTTP for fixtures')
    p.add_argument('--model',help='Model identifier; otherwise BRAIN_PILOT_MODEL or provider default_model')
    credentials=p.add_mutually_exclusive_group()
    credentials.add_argument('--api-key-env',help='Environment variable containing the credential')
    credentials.add_argument('--api-key-file',type=Path,help='Private credential file (contents are never logged)')
    p.add_argument('--env-file',type=Path,help='Explicit dotenv file for ${NAME} references')
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--prepare-only',action='store_true');args=p.parse_args(argv)
    try:
        if args.prepare_only:
            plan=prepare(args.snapshot,args.output,fixture=args.fixture,fixture_label=args.fixture_label)
            print(f"Frozen {len(plan['cases'])}-task replay plan saved")
        else:
            run(args.snapshot,args.output,workers=args.workers,fixture=args.fixture,fixture_label=args.fixture_label,
                config_path=args.config_path,provider_name=args.provider_name,base_url=args.base_url,
                model=args.model,api_key_env=args.api_key_env,api_key_file=args.api_key_file,env_file=args.env_file)
    except (OSError, ValueError, RuntimeError) as exc:
        p.error(str(exc))


if __name__=='__main__':
    main()
