import sys
import hashlib
import json
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/brain-loop/scripts'))
from outbox import Outbox, TransportResult

@pytest.mark.parametrize('reply', [None, {'authorized': False}, {'authorized': True, 'id': 'wrong', 'version': 1}, {'authorized': True, 'id': None, 'version': True}])
def test_untrusted_readback_keeps_upload_held(tmp_path, reply):
    ob = Outbox(tmp_path / 'queue.db')
    jid = ob.enqueue('execution', {'action': 'test'})
    try:
        ob.run_once(lambda job: TransportResult(state='dropped_response_unknown'), owner='one', lease_seconds=10)
        assert ob.reconcile_unknown(jid, lambda *args: reply) == 'unknown'
        assert ob.claim_ready(owner='two', lease_seconds=10) == []
    finally:
        ob.close()

@pytest.mark.parametrize('mode', ['accepted', 'absent', 'unavailable', 'mismatch'])
def test_unknown_requires_exact_authorized_readback(tmp_path, mode):
    ob = Outbox(tmp_path / 'queue.db')
    payload = {'action': 'verified observation'}
    jid = ob.enqueue('execution', payload)
    ob.run_once(lambda job: TransportResult(state='dropped_response_unknown'), owner='one', lease_seconds=10)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    calls = []
    def lookup(kind, identity, version):
        calls.append((kind, identity, version))
        return {'status': mode, 'authorized': True, 'id': jid, 'version': 1, 'digest': digest if mode != 'mismatch' else 'bad'}
    try:
        ob.reconcile_unknown(jid, lookup)
        assert calls == [('execution', jid, 1)]
        assert ob.get(jid).state == {'accepted': 'completed', 'absent': 'pending'}.get(mode, 'unknown')
    finally:
        ob.close()
