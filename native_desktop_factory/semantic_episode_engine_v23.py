"""Additive current episode namespace with semantic native action admission.

The actor loop/reset/scorer/clock and authentic paid-ID hook are reused. A
recoverable native guard rejection consumes one turn; it is never labelled an
applied action. Old v21/v22 namespaces and audit bytes remain unchanged.
"""
from pathlib import Path
import hashlib
import json
import sys
from types import ModuleType
from . import semantic_native_transport_v23 as transport
from .factory import digest
from .official_saved_verifier import verify_official
from .v066_storage_budget import audit as storage_audit

PIN='58ac2f497706f32359edc320970a022ed4cc93916c2f7f77577773e4dd9d2457'
file=Path(__file__).with_name('current_episode_paid_id_v22.py');raw=file.read_bytes()
if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('authentic_paid_episode_wrapper_changed')
source=raw.decode().replace("source=raw.decode()","source=raw.decode().replace('from .pinned_model_load_v21 import load','from .semantic_source_load_v23 import load')").replace('native_desktop_factory._v22_actual_paid_episode','native_desktop_factory._v23_semantic_episode').replace('native_desktop_factory._v22_actual_paid_worker','native_desktop_factory._v23_semantic_worker')
name='native_desktop_factory._v23_semantic_paid_wrapper';module=ModuleType(name);module.__package__='native_desktop_factory';module.__file__=str(file);sys.modules[name]=module
exec(compile(source,name,'exec'),module.__dict__)
# The loader verifies every original replacement exactly once, then adds the
# source-bound recoverable rejection branch.
bound=module._module._bound
bound.transport=transport
from types import FunctionType
base=bound.DesktopProspectiveModelWorker
_episode=base._episode

class DesktopSemanticModelWorker(base):
 def _audit_episode(self,*,batch,out,package,salt,actions):
  task=json.loads(self.integration.controls.private(out/'task.private.json'))
  saved=self.integration.controls.private(out/task['saved_file']);verification=json.loads(self.integration.controls.private(out/'verifier.private.json'))
  independent=verify_official(package['source'],saved,package['oracle'],private_salt=salt)
  self.integration.require(verification['fair_result']==independent and verification['score']==task['score'],'Semantic current saved scorer changed')
  reset=json.loads(self.integration.controls.private(out/'reset.private.json'))
  self.integration.require(reset['actor_guest_sha256']!=reset['reset_guest_sha256'] and reset['actor_terminated'] is reset['reset_terminated'] is True and
   reset['initial_state_sha256']==reset['restored_state_sha256']==digest(package['source']),'Semantic distinct current reset changed')
  actor=batch/Path(task['actor_dir']);clock=json.loads(self.integration.controls.private(out/'actor-clock.private.json'))
  self.integration.require(clock['actor_deadline_monotonic']-clock['actor_started_monotonic']==720 and clock['native_actions_after_deadline']==0,'Semantic current actor clock changed')
  command=json.loads(self.integration.controls.private(actor/'guest-probe-command-v16.private.json'))
  transport.legacy.runtime_policy.verify(json.loads(command['stdout']),self.integration.controls.private(actor/'guest-content-files-v16.jsonl.gz'),json.loads(Path(package['guest_reference_path']).read_bytes()))
  trace=json.loads(self.integration.controls.private(out/'actions.private.json'))
  for row in trace:
   if row.get('status') not in ['applied','rejected']:continue
   step=row['step'];receipt=json.loads(self.integration.controls.private(actor/f'semantic-{step:03d}-receipt.private.json'));transport.guard.validate_receipt(receipt)
   self.integration.require(receipt['status']==row['status'] and receipt['policy_sha256']==transport.POLICY_SHA,'Actual semantic native IO receipt changed')
   for phase in ['observation','predispatch']:
    envelope=json.loads(self.integration.controls.private(actor/f'semantic-{step:03d}-{phase}-envelope.private.json'))
    transport.guard.validate_envelope(envelope)
    for role in ['raw_image','raw_envelope']:
     ref=envelope[role];raw=self.integration.controls.private(batch/'gui'/ref['path']);self.integration.require(digest(raw)==ref['sha256'],'Semantic raw native evidence changed')
  self.integration.require(storage_audit(batch/'gui',verify_all_bytes=True)['unresolved_write_count']==0,'Semantic raw writes unresolved')

integration=module.integration
DesktopSemanticModelWorker.integration=integration
# All actual GUI operations use the same new transport for every slot.
globals_copy={**_episode.__globals__,'transport':transport}
DesktopSemanticModelWorker._episode=FunctionType(_episode.__code__,globals_copy,_episode.__name__,_episode.__defaults__,_episode.__closure__)
PaidCalls=module.PaidCalls
write=module.write
no_regression_passed=module.no_regression_passed
