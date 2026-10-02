"""Additive exact-source native actor clock; the historical guard stays intact."""
import inspect,time,json
from pathlib import Path
from types import ModuleType
from unittest.mock import patch
from tools import office_owned_folder_runtime_v2 as office
from tools import office_owned_folder_native_guard_v2 as original
from tools.office_owned_folder_spool_v2 import NativeOperationSpool
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineProof,ActorDeadlineReached

def deadline(deadline_monotonic):
 now=time.monotonic()
 if now>=deadline_monotonic:
  raise ActorDeadlineReached(ActorDeadlineProof(deadline_monotonic,now,now,0,'actor_deadline_reached_before_submission',False,False))

def _class():
 source=inspect.getsource(original)
 substitutions=[('ContractLimits(max_step=90)','ContractLimits(max_step=90,frame_ttl_seconds=150)'),
  ('    except BaseException:\n','    except ActorDeadlineReached:\n     raise\n    except BaseException:\n')]
 for before,after in substitutions:
  office.require(source.count(before)==1,'Exact original Office guard clock patch changed');source=source.replace(before,after)
 namespace=ModuleType('tools._office_current_native_clock_v4');namespace.__package__='tools';namespace.__file__=original.__file__
 namespace.ActorDeadlineReached=ActorDeadlineReached;exec(compile(source,'office-current-native-clock-v4','exec'),namespace.__dict__)
 return namespace.OwnedNativeActor

_BoundActor=_class()

class Actor(_BoundActor):
 def bind_actor_clock(self,started,absolute_deadline):
  office.require(not hasattr(self,'deadline') and absolute_deadline==started+720,'Exact Office actor deadline required once')
  self.deadline=absolute_deadline;self.host.actor_deadline_epoch_ms=int(time.time()*1000+(absolute_deadline-time.monotonic())*1000)
 def observe(self,**kwargs):deadline(self.deadline);return super().observe(**kwargs)
 def dispatch(self,action):deadline(self.deadline);return super().dispatch(action)
 def reject_model_output(self,text):deadline(self.deadline);return super().reject_model_output(text)

class CurrentOperationSpool(NativeOperationSpool):
 def actor_open(self,*args,**kwargs):
  with patch.object(original,'OwnedNativeActor',Actor):self.actor=super().actor_open(*args,**kwargs)
  return self.actor
 def request(self,operation,payload):
  if operation in ('native_surface','resolve_native_targets','dispatch_native_primitive') and hasattr(getattr(self,'actor',None),'deadline'):
   deadline(self.actor.deadline);payload={**payload,'actor_deadline_epoch_ms':self.actor_deadline_epoch_ms}
  ordinal=self.sequence
  try:return super().request(operation,payload)
  except office.OfficeRuntimeError:
   path=self.root/f'operation-{ordinal:04d}/response.private.json'
   if path.exists() and hasattr(getattr(self,'actor',None),'deadline'):
    record=json.loads(office.private(path));result=record.get('result',{})
    if record.get('status')=='failed' and result.get('actor_deadline_rejected') is True and result.get('native_driver_attempted') is False and result.get('native_operation_may_be_uncertain') is False:
     deadline(self.actor.deadline)
   raise
