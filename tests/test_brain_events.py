from hermes.event_store import Principal
from hermes.knowledge_store import KnowledgeStore
import json
from hermes.brain_events import ReferenceEvents, ANotifyReferenceSender

def test_notifications_retry_without_duplicate_cases(tmp_path):
    s=KnowledgeStore(tmp_path/'db'); p=Principal('a','w','p')
    events=ReferenceEvents(s)
    eid=events.emit(p,'needs-decision','case-1')
    assert events.emit(p,'needs-decision','case-1')==eid
    assert events.deliver_once(p,lambda event:{'delivered':0})['state']=='pending'
    assert events.deliver_once(p,lambda event:{'delivered':1})['state']=='delivered'
    assert events.deliver_once(p,lambda event:None) is None
    s.close()


def test_anotify_sender_transmits_reference_only_and_requires_positive_delivery():
    captured={}
    class Completed:
        returncode=0
        stdout='{"delivered":1}\n200'
    def runner(command,**kwargs):
        captured['command']=command
        captured['kwargs']=kwargs
        return Completed()
    sender=ANotifyReferenceSender('https://notify.invalid/api/notify',token='secret',runner=runner)
    event={'id':'event-1','workspace':'w','project':'p','kind':'conflict','reference':'case-1'}
    assert sender(event)=={'delivered':1}
    body=json.loads(captured['command'][captured['command'].index('-d')+1])
    assert body=={'event':'brain-reference','reference_event':event}
    assert 'Authorization: Bearer secret' in captured['command']


def test_anotify_sender_does_not_treat_2xx_without_receipt_as_delivered():
    class Completed:
        returncode=0
        stdout='{}\n202'
    sender=ANotifyReferenceSender('https://notify.invalid/api/notify',runner=lambda command,**kwargs:Completed())
    event={'id':'event-1','workspace':'w','project':'p','kind':'completed','reference':'task-1'}
    assert sender(event)=={'delivered':0}
