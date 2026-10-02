"""Exact additional semantic rejection branch over the pinned current body."""
from .pinned_model_load_v21 import load as pinned_load

BEFORE="    entry.update(evidence);entry['action_payload_sha256']=digest(result['text'].encode())"
AFTER="""    if evidence.get('native_status')=='rejected':
     entry.update(evidence);entry['action']=action;entry['status']='rejected'
     entry['action_payload_sha256']=digest(result['text'].encode());trace.append(entry)
     write(out/f'step-{step:02d}.private.json',entry)
     memory=action['memory'];previous={'status':'rejected','code':'invalid_action'}
     continue
    entry.update(evidence);entry['action_payload_sha256']=digest(result['text'].encode())"""

def load(filename,name,replacements=()):
 if filename=='prospective_model_worker_v11.py':replacements=(*replacements,(BEFORE,AFTER))
 return pinned_load(filename,name,replacements)
