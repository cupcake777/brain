"""Provider and fixture portability, without external APIs or operator secrets."""
from __future__ import annotations

import hashlib
import json
import os

import httpx
import pytest

from hermes.repository import HermesRepository
from scripts import run_feedback_pilot as pilot


@pytest.fixture(autouse=True)
def isolated_pilot_environment(monkeypatch):
    for name in list(os.environ):
        if name.startswith('BRAIN_PILOT_'):
            monkeypatch.delenv(name)
    monkeypatch.setenv('BRAIN_DISABLE_EMBEDDINGS', '1')


def provider_config(tmp_path, credential='${FIXTURE_CREDENTIAL}'):
    path = tmp_path / 'provider.yaml'
    path.write_text(json.dumps({'providers': {'fixture': {
        'base_url': 'https://model.example/v1', 'api_key': credential,
        'default_model': 'fixture-model'}}}))
    return path


def sample_fixture(tmp_path):
    path = tmp_path / 'cases.json'
    path.write_text(json.dumps({'label': 'portable-synthetic', 'cases': [{
        'id': 'portable-case', 'group': 'custom', 'query': 'fixture lookup',
        'evidence': 'fixture://portable-case', 'prompt': 'Return result.txt with verified.',
        'expected_files': {'result.txt': 'verified'}}]}))
    return path


def snapshot_db(tmp_path):
    path = tmp_path / 'snapshot.sqlite3'
    HermesRepository(path)
    return path


def test_no_implicit_home_configuration_or_provider(monkeypatch):
    monkeypatch.setattr(pilot, '_read_provider_file',
                        lambda *a: pytest.fail('No provider file should be read implicitly'))
    with pytest.raises(ValueError, match='model and base URL'):
        pilot.load_provider()


def test_explicit_yaml_provider_and_process_environment(tmp_path, monkeypatch, capsys):
    config = provider_config(tmp_path)
    monkeypatch.setenv('FIXTURE_CREDENTIAL', 'fixture-credential-value')
    assert pilot.load_provider(config, 'fixture') == (
        'https://model.example/v1', 'fixture-credential-value', 'fixture-model')
    assert capsys.readouterr().out == ''
    with pytest.raises(ValueError, match='Select an existing provider'):
        pilot.load_provider(config)


def test_explicit_legacy_dotenv_and_environment_precedence(tmp_path, monkeypatch):
    config = provider_config(tmp_path)
    environment = tmp_path / 'credential.env'
    environment.write_text('export FIXTURE_CREDENTIAL="fixture-file-value" # fixture only\n')
    assert pilot.load_provider(config, 'fixture', env_file=environment)[1] == 'fixture-file-value'
    monkeypatch.setenv('FIXTURE_CREDENTIAL', 'fixture-process-value')
    assert pilot.load_provider(config, 'fixture', env_file=environment)[1] == 'fixture-process-value'


def test_direct_environment_and_explicit_key_file_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv('BRAIN_PILOT_BASE_URL', 'https://model.example/v1/')
    monkeypatch.setenv('BRAIN_PILOT_MODEL', 'fixture-model')
    monkeypatch.setenv('BRAIN_PILOT_API_KEY', 'fixture-default-key')
    assert pilot.load_provider() == ('https://model.example/v1', 'fixture-default-key', 'fixture-model')
    key_file = tmp_path / 'credential.txt'
    key_file.write_text('fixture-file-key\n')
    assert pilot.load_provider(api_key_file=key_file)[1] == 'fixture-file-key'
    monkeypatch.setenv('BRAIN_PILOT_API_KEY_FILE', str(key_file))
    monkeypatch.setenv('OTHER_FIXTURE_KEY', 'fixture-explicit-env-key')
    assert pilot.load_provider(api_key_env='OTHER_FIXTURE_KEY')[1] == 'fixture-explicit-env-key'
    with pytest.raises(RuntimeError, match='missing or invalid'):
        pilot.load_provider(api_key_env='MISSING_FIXTURE_KEY')


def test_environment_configuration_and_cli_overrides(tmp_path, monkeypatch):
    config = provider_config(tmp_path, credential='fixture-yaml-key')
    monkeypatch.setenv('BRAIN_PILOT_CONFIG', str(config))
    monkeypatch.setenv('BRAIN_PILOT_PROVIDER', 'fixture')
    monkeypatch.setenv('BRAIN_PILOT_BASE_URL', 'https://environment.example/v1')
    monkeypatch.setenv('BRAIN_PILOT_MODEL', 'environment-model')
    assert pilot.load_provider() == ('https://environment.example/v1', 'fixture-yaml-key', 'environment-model')
    assert pilot.load_provider(base_url='http://127.0.0.1:9999/v1', model='override-model') == (
        'http://127.0.0.1:9999/v1', 'fixture-yaml-key', 'override-model')


@pytest.mark.parametrize('origin', ['http://model.example/v1', 'https://user:fixture-secret@model.example/v1',
                                   'https://@model.example/v1', 'https://model.example/v1?key=fixture-secret',
                                   'https://[invalid', 'https://model.example:invalid/v1'])
def test_invalid_endpoint_errors_do_not_echo_credentials(origin, monkeypatch):
    monkeypatch.setenv('BRAIN_PILOT_API_KEY', 'fixture-secret')
    with pytest.raises(ValueError) as error:
        pilot.load_provider(base_url=origin, model='fixture-model')
    assert 'fixture-secret' not in str(error.value)
    assert origin not in str(error.value)


@pytest.mark.parametrize('malformed', ['providers: [fixture-secret',
                                      'providers:\n  fixture: null',
                                      'providers:\n  fixture: [fixture-secret]'])
def test_invalid_provider_yaml_has_sanitized_errors(tmp_path, malformed):
    path = tmp_path / 'bad.yaml'
    path.write_text(malformed)
    with pytest.raises(ValueError) as error:
        pilot.load_provider(path, 'fixture')
    assert 'fixture-secret' not in str(error.value)


def test_bad_dotenv_quoting_does_not_echo_secret(tmp_path):
    config = provider_config(tmp_path)
    environment = tmp_path / 'bad.env'
    environment.write_text('FIXTURE_CREDENTIAL="fixture-secret\n')
    with pytest.raises(ValueError, match='quoting') as error:
        pilot.load_provider(config, 'fixture', env_file=environment)
    assert 'fixture-secret' not in str(error.value)


def test_prepare_external_fixture_leaves_source_snapshot_unchanged(tmp_path, monkeypatch):
    snapshot = snapshot_db(tmp_path)
    before = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    fixture = sample_fixture(tmp_path)
    monkeypatch.setattr(pilot, 'load_provider', lambda *a, **k: pytest.fail('Preparation needs no credentials'))
    output = tmp_path / 'prepared'
    pilot.main(['--snapshot', str(snapshot), '--output', str(output),
                '--fixture', str(fixture), '--prepare-only'])
    plan = json.loads((output / 'frozen-plan.json').read_text())
    assert plan['fixture_label'] == 'portable-synthetic'
    assert len(plan['cases']) == 1
    assert plan['cases'][0]['candidates'] == []
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == before
    assert not (output / 'schedule.json').exists()
    with pytest.raises(RuntimeError, match='Frozen plan changed'):
        pilot.prepare(snapshot, output, fixture=fixture, fixture_label='different-source')


def test_historical_defaults_are_labelled_and_old_frozen_plans_remain_usable(tmp_path):
    snapshot = snapshot_db(tmp_path)
    output = tmp_path / 'historical'
    plan = pilot.prepare(snapshot, output)
    assert plan['fixture_label'] == 'historical-deployment-20261127'
    assert len(plan['cases']) == 12
    old = dict(plan)
    old.pop('fixture_label')
    (output / 'frozen-plan.json').write_text(json.dumps(old))
    assert pilot.prepare(snapshot, output) == plan


@pytest.mark.parametrize('change', [
    {'id': '../outside'}, {'id': 'same', 'expected_files': {'../outside': 'text'}},
    {'id': 'same', 'expected_files': {'C:\\outside': 'text'}},
    {'id': 'same', 'expected_files': []}, {'id': 'unknown', 'expected_files': None},
])
def test_invalid_external_fixtures_are_rejected(tmp_path, change):
    fixture = sample_fixture(tmp_path)
    data = json.loads(fixture.read_text())
    data['cases'][0].update(change)
    fixture.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        pilot.load_fixture(fixture)


def test_external_exact_file_assertion_never_executes_content():
    files = {'result.sh': 'exit 99\n'}
    assert pilot.judge({'expected_files': files}, dict(files)) is True
    assert pilot.judge({'expected_files': files}, {**files, 'extra': ''}) is False


def test_cli_runs_both_arms_with_mocked_provider_and_no_secret_output(tmp_path, monkeypatch, capsys):
    snapshot = snapshot_db(tmp_path)
    fixture = sample_fixture(tmp_path)
    config = provider_config(tmp_path)
    key_file = tmp_path / 'credential.txt'
    key_file.write_text('fixture-private-key')
    calls = []

    def post(url, *, json, headers, timeout):
        assert url == 'https://model.example/v1/chat/completions'
        assert headers['Authorization'] == 'Bearer fixture-private-key'
        assert json['model'] == 'explicit-model'
        assert timeout == 110
        calls.append(json)
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'choices': [{'message': {'content': '{"files":{"result.txt":"verified"}}'}}],
            'usage': {'total_tokens': 7}, 'model': 'explicit-model'})

    monkeypatch.setattr(pilot.httpx, 'post', post)
    output = tmp_path / 'runs'
    args = ['--snapshot', str(snapshot), '--output', str(output), '--fixture', str(fixture),
            '--config', str(config), '--provider', 'fixture', '--model', 'explicit-model',
            '--api-key-file', str(key_file), '--workers', '1']
    pilot.main(args)
    assert len(calls) == 2
    result = json.loads((output / 'results.json').read_text())
    assert result['fixture_label'] == 'portable-synthetic'
    assert result['summary']['on']['accepted'] == result['summary']['off']['accepted'] == 1
    assert result['summary']['on']['by_group'] == {'custom': 1}
    assert result['summary']['off']['total_tokens'] == 7
    pilot.main(args)
    assert len(calls) == 2
    assert 'fixture-private-key' not in capsys.readouterr().out
    assert all('fixture-private-key' not in p.read_text() for p in output.glob('*.json'))
    with pytest.raises(SystemExit):
        pilot.main([*args, '--model', 'different-model'])
    assert len(calls) == 2


def test_http_error_does_not_persist_response_body_or_credential(tmp_path, monkeypatch, capsys):
    snapshot = snapshot_db(tmp_path)
    fixture = sample_fixture(tmp_path)
    monkeypatch.setenv('BRAIN_PILOT_API_KEY', 'fixture-private-key')

    def post(url, **kwargs):
        return httpx.Response(401, request=httpx.Request('POST', url),
                              text='fixture-private-key provider error body')

    monkeypatch.setattr(pilot.httpx, 'post', post)
    output = tmp_path / 'failed'
    pilot.run(snapshot, output, fixture=fixture,
              base_url='https://model.example/v1', model='fixture-model', workers=1)
    assert 'fixture-private-key' not in capsys.readouterr().out
    for path in output.glob('*.json'):
        assert 'fixture-private-key' not in path.read_text()
    result = json.loads((output / 'results.json').read_text())
    assert result['summary']['on']['accepted'] == 0
    assert result['summary']['on']['errors'] == 1
