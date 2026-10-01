"""One semantic native transport for teacher, controls, base and four CPs."""
from pathlib import Path
import time
from cursibench.scale_action_output_v066 import normalize_model_action
from . import semantic_episode_engine_v23 as engine
from . import semantic_native_transport_v23 as transport
from . import current_teacher_worker_v22 as teacher

class SemanticTeacherEpisode(teacher.CurrentTeacherEpisode):
 _episode=engine.DesktopSemanticModelWorker._episode
 _audit_episode=engine.DesktopSemanticModelWorker._audit_episode
 integration=engine.integration
 def __init__(self):super().__init__(guest_factory=transport.create_guest)

class DesktopSemanticTeacherWorker(teacher.DesktopCurrentTeacherWorker):
 def _run_current(self,**kwargs):
  kwargs['episode']=SemanticTeacherEpisode()
  return super()._run_current(**kwargs)

class SemanticControlDriver:
 """A reference control receives no bypass around the same current gate."""
 def __init__(self,*,actor,identity,instruction,actor_deadline):
  if type(actor) is not transport.SemanticModelGuest:raise ValueError('Real semantic native actor required')
  self.actor,self.identity,self.instruction,self.deadline=actor,identity,instruction,actor_deadline
  self.step=0;self.previous=None;self.memory=''
 def dispatch(self,model_action_json):
  if self.step>=90 or time.monotonic()>=self.deadline:raise ValueError('Uniform native control actor budget exhausted')
  observation=self.actor.observe(identity=self.identity,instruction=self.instruction,step=self.step,previous=self.previous,memory=self.memory)
  action,evidence=self.actor.dispatch_model(model_action_json,observation,actor_deadline=self.deadline)
  self.previous={'status':evidence['native_status'],'code':'ok' if evidence['native_status']=='applied' else 'invalid_action'};self.memory=action['memory'];self.step+=1
  return action,evidence
