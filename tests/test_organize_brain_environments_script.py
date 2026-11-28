"""Portable environment maintenance against disposable databases only."""
from __future__ import annotations

import json

import pytest

from hermes.integrate import integrate
from hermes.repository import HermesRepository
from scripts import organize_brain_environments as organizer


@pytest.fixture
def maintenance_db(tmp_path, monkeypatch):
    monkeypatch.setenv('BRAIN_DISABLE_EMBEDDINGS', '1')
    repo = HermesRepository(tmp_path / 'fixture.sqlite3')
    node_ids = []
    for content in ('Check fixture alpha before reuse.', 'Preserve independent fixture beta.'):
        node = integrate(content=content, source='test://maintenance', category='rule',
                         domain='tech', evidence=['test://maintenance'], repo=repo)
        repo.update_knowledge_node(node.node_id, stage='verified')
        node_ids.append(node.node_id)
    assert len(set(node_ids)) == 2
    return repo, node_ids


def test_default_apply_never_retires_nodes(maintenance_db, tmp_path, capsys):
    repo, node_ids = maintenance_db
    output = tmp_path / 'report.json'
    organizer.organize(repo.db_path, output, apply=True)
    report = json.loads(output.read_text())
    assert report['applied'] is True
    assert report['retire_exact_nodes'] == {}
    assert all(repo.get_knowledge_node(node_id).stage == 'verified' for node_id in node_ids)
    assert json.loads(capsys.readouterr().out)['retire_ids'] == 0


def test_explicit_manifest_retires_only_selected_node(maintenance_db, tmp_path):
    repo, (selected, untouched) = maintenance_db
    manifest = tmp_path / 'retirements.json'
    manifest.write_text(json.dumps({selected: 'Superseded by an independently checked fixture.'}))
    output = tmp_path / 'report.json'
    organizer.main(['--db', str(repo.db_path), '--output', str(output),
                    '--retire-manifest', str(manifest), '--apply'])
    assert repo.get_knowledge_node(selected).stage == 'deprecated'
    assert repo.get_knowledge_node(untouched).stage == 'verified'
    assert json.loads(output.read_text())['retire_exact_nodes'] == json.loads(manifest.read_text())


def test_explicit_manifest_still_requires_apply(maintenance_db, tmp_path):
    repo, (selected, _) = maintenance_db
    output = tmp_path / 'report.json'
    decisions = {selected: 'Fixture retirement reason.'}
    organizer.organize(repo.db_path, output, retire_nodes=decisions)
    report = json.loads(output.read_text())
    assert report['applied'] is False
    assert report['retire_exact_nodes'] == decisions
    assert repo.get_knowledge_node(selected).stage == 'verified'


@pytest.mark.parametrize('decisions', [[], 'node', {'': 'reason'}, {' node': 'reason'},
                                       {'node': ''}, {'node': '   '}, {'node': None}])
def test_invalid_manifest_is_rejected_before_database_access(tmp_path, monkeypatch, decisions):
    def unexpected_database_access(*args, **kwargs):
        pytest.fail('Invalid decisions must be rejected before opening the database')
    monkeypatch.setattr(organizer.sqlite3, 'connect', unexpected_database_access)
    with pytest.raises(ValueError, match='retirement|review reason'):
        organizer.organize(tmp_path / 'missing.sqlite3', tmp_path / 'report.json',
                           apply=True, retire_nodes=decisions)
    assert not (tmp_path / 'report.json').exists()


def test_null_json_manifest_is_rejected(tmp_path):
    manifest = tmp_path / 'null.json'
    manifest.write_text('null')
    with pytest.raises(ValueError, match='JSON object'):
        organizer.main(['--db', str(tmp_path / 'missing.sqlite3'),
                        '--output', str(tmp_path / 'report.json'),
                        '--retire-manifest', str(manifest)])
