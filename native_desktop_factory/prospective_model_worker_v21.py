"""Same uniform episode/scorer with proven actor-deadline handling before GUI."""
import json
from pathlib import Path
from .pinned_model_load_v21 import load
from . import model_transport_integration_v21 as integration
from . import deadline_model_transport_v21 as transport
from .actor_deadline_future_v21 import ActorDeadlineReached
from .factory import digest

_budget_branch="""    try:
     result,result_sha,paid_id=paid.invoke(suffix=f'sample-{ordinal:03d}-{step:03d}',category='tinker',
                                        identity=identity,request=request,provider=provider)
    except ActorDeadlineReached as exc:
     proof=sampler.assert_deadline_stop(deadline)
     integration.require(proof==exc.proof.receipt() and not actor.killed,'v21_deadline_guest_or_proof_changed')
     budget_ref=write(out/'actor-budget-stop.private.json',{
      'schema':'cua-native-actor-budget-stop-v21','actor_deadline_proof':proof,
      'sample_paid_attempt_id':paid.attempt_id+f'-sample-{ordinal:03d}-{step:03d}',
      'gui_applied':False,'same_request_replay_authorized':False,'official_final_credit':0})
     trace.append({'step':step,'sampled_frame':sampled_ref,'status':'not_applied_actor_deadline',
       'actor_budget_stop_sha256':budget_ref['sha256'],'model_error_code':None})
     model_outcome='actor_wall_budget';break
"""

_clock_branch="""   actor_elapsed_raw=time.monotonic()-actor_started
   # The action clock stops at its deadline. RPC acknowledgement/evaluation
   # latency is separately retained; no native action can start or finish late.
   actor_elapsed=min(actor_elapsed_raw,720) if model_outcome=='actor_wall_budget' else actor_elapsed_raw
   actor_clock=write(out/'actor-clock.private.json',{
    'schema':'cua-native-actor-clock-v21','actor_started_monotonic':actor_started,
    'actor_deadline_monotonic':deadline,'raw_elapsed_until_ack_seconds':actor_elapsed_raw,
    'actor_elapsed_seconds':actor_elapsed,'model_outcome':model_outcome,
    'native_actions_after_deadline':0,'evaluation_outside_actor_clock':True})
"""

_bound=load('prospective_model_worker_v11.py','native_desktop_factory._v21_bound_worker',[
 ('    if remaining<1:model_outcome=\'actor_wall_budget\';break',
  '    if remaining<=0:model_outcome=\'actor_wall_budget\';break'),
 ('task_dir=out,remaining_seconds=deadline-time.monotonic())',
  'task_dir=out,remaining_seconds=deadline-time.monotonic(),actor_deadline=deadline)'),
 ("    result,result_sha,paid_id=paid.invoke(suffix=f'sample-{ordinal:03d}-{step:03d}',category='tinker',\n                                        identity=identity,request=request,provider=provider)\n",_budget_branch),
 ('   actor_elapsed=time.monotonic()-actor_started\n',_clock_branch),
 ("    except TimeoutError:model_outcome='actor_wall_budget';trace.append(entry);break",
  "    except TimeoutError as exc:\n     if str(exc)!='v11_actor_wall_budget' or time.monotonic()<deadline:raise\n     model_outcome='actor_wall_budget';trace.append(entry);break"),
 ("    entry['action']=action;entry['status']='applied';trace.append(entry);actions.append(action)",
  "    integration.require(time.monotonic()<=deadline,'v21_native_gui_finished_after_actor_deadline')\n    entry['dispatch_finished_monotonic']=time.monotonic()\n    entry['action']=action;entry['status']='applied';trace.append(entry);actions.append(action)"),
 ("    'turn_count':len(trace),'actor_elapsed_seconds':actor_elapsed,'saved_file':saved_path.name,",
  "    'turn_count':len(trace),'actor_elapsed_seconds':actor_elapsed,'actor_clock_sha256':actor_clock['sha256'],'saved_file':saved_path.name,"),
 ("  write(self.root/'paid'/(paid_id+'.request.private.json'),request)\n",
  "  write(self.root/'paid'/(paid_id+'.request.private.json'),request)\n  self.ids.append(paid_id) # Include consumed uncertain requests in formal coverage.\n"),
 ('  self.ids.append(paid_id)\n  self.calls.append(', '  self.calls.append('),
])
_bound.integration=integration;_bound.transport=transport;_bound.ActorDeadlineReached=ActorDeadlineReached
_legacy_audit=_bound.DesktopProspectiveModelWorker._audit_episode


def _audit(self,*,batch,out,package,salt,actions):
    _legacy_audit(self,batch=batch,out=out,package=package,salt=salt,actions=actions)
    task=json.loads(integration.controls.private(out/'task.private.json'))
    raw=integration.controls.private(out/'actor-clock.private.json');clock=json.loads(raw)
    trace=json.loads(integration.controls.private(out/'actions.private.json'))
    integration.require(digest(raw)==task['actor_clock_sha256'] and
        clock['actor_deadline_monotonic']-clock['actor_started_monotonic']==720 and
        clock['actor_elapsed_seconds']==task['actor_elapsed_seconds'] and
        clock['native_actions_after_deadline']==0 and
        all(r['dispatch_finished_monotonic']<=clock['actor_deadline_monotonic'] for r in trace if r.get('status')=='applied'),
        'v21_actor_clock_or_native_completion_changed')
    if any(r.get('status')=='not_applied_actor_deadline' for r in trace):
        budget_raw=integration.controls.private(out/'actor-budget-stop.private.json')
        budget=json.loads(budget_raw)
        transport.checked_deadline_proof(budget['actor_deadline_proof'],clock['actor_deadline_monotonic'])
        integration.require(clock['actor_elapsed_seconds']==720 and clock['raw_elapsed_until_ack_seconds']>=720 and
            budget['gui_applied'] is False and
            all(r['actor_budget_stop_sha256']==digest(budget_raw) for r in trace if r.get('status')=='not_applied_actor_deadline'),
            'v21_budget_stop_artifacts_changed')


_bound.DesktopProspectiveModelWorker._audit_episode=_audit
DesktopProspectiveModelWorker=_bound.DesktopProspectiveModelWorker
PaidCalls=_bound.PaidCalls
write=_bound.write
no_regression_passed=_bound.no_regression_passed
