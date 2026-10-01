"""Exact current v21 episode with a uniform authentic paid-ID hook.

Only the deadline evidence identity changes. Native actions, 90/720/1200
limits, saved-state scorer, readiness and distinct reset remain the exact
current engine. Frozen v21 modules are neither edited nor monkey-patched.
"""
from pathlib import Path
import hashlib
import json
import sys
from types import ModuleType

PIN='13a2fd3f8ad7ee83047d83967300653631b3a05f486e1f2b1554aa20b7454105'
source_path=Path(__file__).with_name('prospective_model_worker_v21.py')
raw=source_path.read_bytes()
if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('current_v21_episode_source_changed')
source=raw.decode()
replacements={
 "'sample_paid_attempt_id':paid.attempt_id+f'-sample-{ordinal:03d}-{step:03d}',":"'sample_paid_attempt_id':paid.actual_sample_attempt_id(ordinal=ordinal,step=step),",
 "'native_desktop_factory._v21_bound_worker'":"'native_desktop_factory._v22_actual_paid_worker'",
}
for before,after in replacements.items():
 if source.count(before)!=1:raise ValueError('actual_paid_id_hook_not_exactly_once')
 source=source.replace(before,after)
_namespace='native_desktop_factory._v22_actual_paid_episode'
_module=ModuleType(_namespace);_module.__package__='native_desktop_factory';_module.__file__=str(source_path)
sys.modules[_namespace]=_module
try:exec(compile(source,_namespace,'exec'),_module.__dict__)
except BaseException:sys.modules.pop(_namespace,None);raise

DesktopProspectiveModelWorker=_module.DesktopProspectiveModelWorker
write=_module.write
no_regression_passed=_module.no_regression_passed
integration=_module.integration
transport=_module.transport

class PaidCalls(_module.PaidCalls):
 """A candidate ID becomes authentic only after its actual private intent."""
 def invoke(self,*,suffix,category,request,provider,identity=None):
  self.last_attempt_id=self.attempt_id+'-'+suffix
  return super().invoke(suffix=suffix,category=category,request=request,provider=provider,identity=identity)
 def actual_sample_attempt_id(self,*,ordinal,step):
  identifier=getattr(self,'last_attempt_id',None)
  expected=self.attempt_id+f'-sample-{ordinal:03d}-{step:03d}'
  integration.require(identifier==expected,'actual_consumed_model_paid_id_missing')
  folder=self.root/'paid';intent_path=folder/(identifier+'.intent.private.json');request_path=folder/(identifier+'.request.private.json');dispatched_path=folder/(identifier+'.dispatched.private.json')
  intent_raw=integration.controls.private(intent_path);intent=json.loads(intent_raw);request_raw=integration.controls.private(request_path);request=json.loads(request_raw);dispatched=json.loads(integration.controls.private(dispatched_path))
  integration.require(intent['attempt_id']==identifier and intent['category']=='tinker' and intent['request_sha256']==hashlib.sha256(request_raw).hexdigest() and
   request['step']==step and dispatched['intent_sha256']==hashlib.sha256(intent_raw).hexdigest(),'actual_model_paid_intent_or_dispatch_changed')
  if self.session is not None:
   self.session._audit_paid_files();events=[r['data'] for r in self.session._events('paid_intent') if r['data']['attempt_id']==identifier]
   integration.require(len(events)==1 and events[0]['category']=='tinker' and events[0]['request_sha256']==intent['request_sha256'],'actual_model_paid_session_provenance_missing')
  return identifier

# Class-local replacement in this isolated source namespace only. All five
# student slots must bind this same wrapper in the fresh v22 source registry.
_module._bound.PaidCalls=PaidCalls
