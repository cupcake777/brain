"""Direct outbox acknowledgement must match the exact stored version."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/brain-loop/scripts'))
from outbox import Outbox, StaleJobError

@pytest.mark.parametrize('ack', [None, True, 2, 0, '1'])
def test_direct_ack_rejects_nonexact_version(tmp_path, ack):
    ob = Outbox(tmp_path / 'queue.sqlite3')
    try:
        job_id = ob.enqueue('execution', {'action': 'test'})
        with pytest.raises(StaleJobError):
            ob.record_success(job_id, acknowledged_version=ack, response=None)
        assert ob.get(job_id).state == 'pending'
    finally:
        ob.close()
