"""Current episode/scorer/reset reused with one concrete common native guest.

All five student slots and teacher/control use the same bootstrap, reader,
semantic guard and native IO. Native activation precedes any paid dispatch.
Historical engines remain unchanged; constructors perform no provider calls.
"""
from pathlib import Path
import json
from types import FunctionType
from . import semantic_episode_engine_v23 as current
from . import semantic_native_counterparts_v23 as counterparts
from . import current_teacher_worker_v22 as teacher
from . import common_native_guest_v31 as native
from .factory import digest


def bound(function,**replacements):
 result=FunctionType(function.__code__,{**function.__globals__,**replacements},function.__name__,function.__defaults__,function.__closure__)
 result.__kwdefaults__=function.__kwdefaults__;return result

class DesktopCommonNativeWorker(current.DesktopSemanticModelWorker):
 _episode=bound(current.DesktopSemanticModelWorker._episode,transport=native)
 _create=bound(current.DesktopSemanticModelWorker._create,transport=native)
 def __init__(self,*args,native_factory,**kwargs):
  if not isinstance(native_factory,native.CommonGuestFactory):raise ValueError('Actual common native guest factory required')
  self.native_factory=native_factory;super().__init__(*args,**kwargs)
 def _gate(self):
  self.native_factory.require_activation()
  return super()._gate()
 def run_selection(self,**kwargs):
  with native.runtime_context(self.native_factory):return super().run_selection(**kwargs)
 def run_base_selection(self,**kwargs):
  with native.runtime_context(self.native_factory):return super().run_base_selection(**kwargs)
 def run_once(self,*args,**kwargs):
  with native.runtime_context(self.native_factory):return super().run_once(*args,**kwargs)
 def _audit_episode(self,**kwargs):
  current.DesktopSemanticModelWorker._audit_episode(self,**kwargs)
  task=json.loads(self.integration.controls.private(kwargs['out']/'task.private.json'))
  for name in ['actor_dir','reset_dir']:
   directory=kwargs['batch']/task[name]
   manifest_raw=self.integration.controls.private(directory/'native-source-manifest.private.json');manifest=json.loads(manifest_raw)
   self.integration.require(manifest==self.native_factory.manifest,'Common native per-guest source manifest differs')
   command=json.loads(self.integration.controls.private(directory/'guest-probe-command-v16.private.json'));base=json.loads(command['stdout'])
   expected=native.supplemental.supplemental_attestation(prefix=directory/'native-supplemental-content.private',base_content_tree_sha256=base['content_tree_sha256'],source_manifest_sha256=digest(native.canonical(manifest)))
   observed=json.loads(self.integration.controls.private(directory/'native-supplemental-epoch.private.json'))
   self.integration.require(observed==expected,'Actual base/supplemental native guest binding differs')
   receipt=json.loads(self.integration.controls.private(directory/'guest.private.json'))
   self.integration.require(receipt['supplemental_content_epoch_sha256']==expected['supplemental_content_epoch_sha256'] and receipt['native_common_actor_paths']==list(native.ACTOR_PATHS),'Native shared actor receipt differs')

class CommonNativeTeacherEpisode(teacher.CurrentTeacherEpisode):
 _episode=DesktopCommonNativeWorker._episode
 _audit_episode=DesktopCommonNativeWorker._audit_episode
 integration=current.integration
 def __init__(self,*,native_factory):
  self.native_factory=native_factory;super().__init__(guest_factory=native_factory.create_guest)

class DesktopCommonNativeTeacherWorker(teacher.DesktopCurrentTeacherWorker):
 def __init__(self,*args,native_factory,**kwargs):
  if not isinstance(native_factory,native.CommonGuestFactory):raise ValueError('Common native teacher factory required')
  self.native_factory=native_factory;super().__init__(*args,**kwargs);self.sources=self.native_factory.manifest['source_sha256s']
 def _gate(self,task):
  self.native_factory.require_activation()
  return super()._gate(task)
 def _run_current(self,**kwargs):
  kwargs['episode']=CommonNativeTeacherEpisode(native_factory=self.native_factory)
  return super()._run_current(**kwargs)

class CommonNativeControlDriver(counterparts.SemanticControlDriver):
 def __init__(self,*,actor,identity,instruction,actor_deadline):
  if type(actor) is not native.CommonNativeModelGuest:raise ValueError('Actual common native control actor required')
  # Reuse the same dispatch body without the obsolete exact V23 class check.
  self.actor,self.identity,self.instruction,self.deadline=actor,identity,instruction,actor_deadline
  self.step=0;self.previous=None;self.memory=''

def source_registration(*,root,native_epoch_sha256):
 from cursibench.full_study_native_counterparts_v22 import register
 sources=native.source_manifest(root)['source_sha256s']
 return register(root,cell_id='desktop-native',native_source_sha256s=sources,
  actor_clock_source_sha256=sources['native_desktop_factory/actor_deadline_future_v21.py'],native_epoch_sha256=native_epoch_sha256,qualified=False)
