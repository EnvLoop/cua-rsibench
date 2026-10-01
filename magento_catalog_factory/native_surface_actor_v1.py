"""One clean original-Magento episode for every teacher/base/checkpoint slot."""
from __future__ import annotations
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import time
from types import SimpleNamespace
from cursibench import native_surface_guard_policy_v1 as policy
from cursibench.scale_action_contract import ContractError
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from tools import magento_dedicated_train_lane_v066 as original
from . import verify
from .native_surface_guard_v1 import NativeAdapter,NATIVE_JS
from .native_surface_lease_v1 import OwnedOperation,LeaseBoundary
from .native_command_journal_v2 import CommandJournal as NativeCommandJournal


async def run_task(*,case,task,output,runtime,sampler,username,attempt_id,paid_attempt_id):
    """Runtime and sampler are concrete source-bound providers, never actor tools."""
    from .native_surface_workers_v1 import public_binding
    source_binding=public_binding()['binding_sha256']
    output=Path(output);started=time.monotonic();session=None;adapter=None;frames=[];actions=[];samples=[]
    deadline_error=None;termination='unknown';saved=None;score=None
    operation=OwnedOperation(output.parent/'magento-native-operation.lock')
    with operation:
        try:
            async with runtime.open_case(case,output) as active:
                session=active
                verify.check_baseline(case,active.baseline_state)
                initial=await active.page.evaluate(NATIVE_JS,[])
                if initial['native_username']!=username or initial['account_witness']['visible_count']!=1:
                    raise policy.GuardError('magento_native_username_witness_missing')
                start=time.monotonic()
                from enterprise_fallback.odoo18.odoo_native_surface_evidence_v6 import EvidenceStore
                store=EvidenceStore(output)
                prepared=runtime.prepared_for_current_episode
                boundary=LeaseBoundary(session=active,operation=operation,username=username,page=active.page,
                    store=store,started=start,deadline=start+720,prepared=prepared)
                adapter=NativeAdapter(page=active.page,task_id=task['task_id'],package_sha256=task['package_sha256'],
                    instruction=case['instruction'],root=output,lease_boundary=boundary)
                sampler.actor_clock=adapter.actor;sampler.parent_paid_attempt_id=paid_attempt_id
                if hasattr(sampler,'bind_native_adapter'):sampler.bind_native_adapter(adapter,asyncio.get_running_loop())
                memory=''
                for step in range(90):
                    observation=None;intent=None;sample_started=None;request_paid_id=paid_attempt_id
                    try:
                        observation,_rendered=await adapter.observe(memory)
                        frame=adapter.store.write(f'frames/step-{step:03d}.png',observation.screenshot_bytes,'raw_observation_image')
                        frames.append({'step':step,'frame_id':observation.frame_id,'frame':frame,
                            'native_envelope':adapter.store.json(f'frames/step-{step:03d}-envelope.private.json',adapter.observed,'native_observation_envelope')})
                        request_id=sampler.request_id_for_step(step) if hasattr(sampler,'request_id_for_step') else 'odoo-sel-'+sha256(sampler.attempt_id.encode()).hexdigest()[:10]+f'-00-{step:03d}'
                        request_paid_id=sampler.next_paid_attempt_id(step) if hasattr(sampler,'next_paid_attempt_id') else paid_attempt_id
                        intent=adapter.store.json(f'paid/sample-{step:03d}-intent.private.json',{
                            'request_id':request_id,'paid_attempt_id':request_paid_id,'task_id':task['task_id'],
                            'package_sha256':task['package_sha256'],'frame_id':observation.frame_id,
                            'frame_sha256':observation.screenshot['sha256'],'same_request_replay_authorized':False},'action_intent')
                        sample_started=time.monotonic()
                        if type(sampler).__module__=='magento_catalog_factory.native_surface_facade_v1' and getattr(sampler,'trusted_control',False):
                            result={'status':'control_action','text':json.dumps(await sampler.control_sample(observation)),
                                'request_id':request_id,'paid_attempt_id':None,'model_call_performed':False}
                        else:result=await asyncio.to_thread(sampler.sample,observation,task_index=0,step=step,task_dir=output)
                        result_ref=adapter.store.json(f'paid/sample-{step:03d}-result.private.json',result,'driver_result')
                        samples.append({'step':step,'raw_result':result,'request_id':result.get('request_id'),
                            'paid_attempt_id':result.get('paid_attempt_id',paid_attempt_id),'status':result.get('status'),'intent':intent,'result':result_ref,
                            'provider_latency_ms':round((time.monotonic()-sample_started)*1000)})
                        if result.get('status')!='control_action' and (result.get('status')!='completed' or result.get('reused') or result.get('new_dispatch') is not True):
                            raise policy.GuardError('magento_provider_result_unknown_no_replay')
                        dispatch=await adapter.dispatch(result['text'])
                        actions.append({'step':step,'status':dispatch['status'],'action':dispatch['action'],
                            'contract':dispatch['contract'],'observed_image':frame})
                        if dispatch['status']=='rejected' and type(sampler).__module__=='magento_catalog_factory.native_surface_facade_v1':
                            raise policy.GuardError('trusted_reference_rejected_no_replay')
                        memory=dispatch['action']['memory']
                        if dispatch['finished']:termination='model_finish';break
                    except ActorDeadlineReached as error:
                        deadline_error=error;termination='task_wall_budget'
                        if observation is not None and getattr(sampler,'last_deadline_result',None) is not None:
                            samples.append({'step':step,'raw_result':sampler.last_raw_result,'request_id':sampler.last_request_id,
                                'paid_attempt_id':sampler.ids[-1] if getattr(sampler,'ids',None) else paid_attempt_id,'status':'actor_deadline_proven','intent':intent,'result':None,
                                'deadline_evidence':sampler.last_deadline_reference,'provider_latency_ms':round((time.monotonic()-sample_started)*1000)})
                        adapter.store.json('actor-clock/budget-stop.private.json',{
                            'schema':'magento-actual-actor-budget-stop-v1','task_id':task['task_id'],
                            'package_sha256':task['package_sha256'],'actor_deadline_proof':error.proof.receipt(),
                            'gui_applied':False,'same_request_replay_authorized':False,
                            'request_id':getattr(sampler,'last_request_id',None),'paid_attempt_id':request_paid_id},'dispatch_receipt')
                        break
                    except ContractError as error:
                        termination='invalid_model_action'
                        adapter.store.json('actor-clock/invalid-model-action.private.json',{'error_code':error.code,'native_io_not_attempted':True},'dispatch_receipt')
                        break
                else:termination='task_action_budget'
                adapter.actor.end(termination,deadline_exception=deadline_error)
                saved=await active.saved_state()
                if saved.get('native_save_observed') is not True:raise policy.GuardError('magento_saved_readback_missing')
                score=verify.score_saved_state(case,active.baseline_state,saved['snapshot'])
                adapter.store.json('saved-state.private.json',saved,'native_observation_envelope')
                adapter.store.json('verifier.private.json',{'schema':'magento-native-saved-verifier-v1',
                    'task_id':task['task_id'],'package_sha256':task['package_sha256'],'verdict':score,
                    'baseline':active.baseline_state,'case':case},'native_observation_envelope')
        except BaseException as error:
            from enterprise_fallback.odoo18.odoo_native_surface_evidence_v6 import EvidenceStore
            EvidenceStore(output).json('failure.private.json',{'schema':'magento-native-terminal-failure-v1',
                'task_id':task['task_id'],'package_sha256':task['package_sha256'],'error_type':type(error).__name__,
                'error_code':getattr(error,'code',None),'actual_error_text':str(error),'saved_score_not_inferred':True,
                'applied_not_inferred':True,'same_request_replay_authorized':False},'dispatch_receipt')
            raise
        finally:
            if adapter is not None:
                adapter.store.json('frames.private.json',{'frames':frames},'native_observation_envelope')
                adapter.store.json('actions.private.json',{'actions':actions},'native_observation_envelope')
                adapter.store.json('samples.private.json',{'samples':samples,'typed_deadline':deadline_error is not None},'native_observation_envelope')
    if session is None or saved is None or score is None or session.reset_proof is None:
        raise policy.GuardError('magento_owned_saved_reset_missing')
    proof=session.reset_proof
    if not all(proof.get(k) is True for k in ('fresh_clone_reset_passed','different_app_container_ids',
        'different_search_container_ids','no_host_mounts','both_pairs_removed')):
        raise policy.GuardError('magento_fresh_clone_reset_or_cleanup_unproved')
    verify.check_material_reset(session.baseline_state,proof['restored_snapshot'])
    adapter.store.json('reset.private.json',proof,'native_observation_envelope')
    ended=time.monotonic()
    if ended-started>1200:raise policy.GuardError('magento_owned_lifecycle_exceeded_1200')
    adapter.store.json('lifecycle.private.json',{'schema':'magento-owned-task-lifecycle-v1',
        'attempt_id':attempt_id,'started_monotonic':started,'reset_cleanup_ended_monotonic':ended,
        'actor_clock':adapter.actor.end_ref,'actor_wall_time_ms':round((adapter.actor.ended-adapter.actor.started)*1000),
        'provider_close_not_inferred':True,'owned_lease_seconds_limit':1200},'native_observation_envelope')
    return {'native_source_binding_sha256':source_binding,'task_id':task['task_id'],'package_sha256':task['package_sha256'],'score':int(score['score']==1.0),
        'termination':termination,'actor_clock_ref':adapter.actor.end_ref,'action_count':sum(r['status']=='applied' for r in actions),
        'turn_count':len(frames),'actor_wall_time_ms':round((adapter.actor.ended-adapter.actor.started)*1000),
        'provider_latency_ms':sum(r['provider_latency_ms'] for r in samples),
        'lifecycle_wall_time_ms':round((ended-started)*1000),'samples':samples,'baseline':session.baseline_state,
        'saved':saved,'reset':proof,'verdict':score}


class Runtime(original.DedicatedMagentoTrainRuntime):
    """Original real clean-clone lifecycle with observable prepared identities."""
    @__import__('contextlib').asynccontextmanager
    async def open_case(self,case,out_dir):
        original_prepare=original.DedicatedCloneManager.prepare
        runtime=self
        def prepare(manager,spec,**kwargs):
            result=original_prepare(manager,spec,**kwargs)
            if spec.index==0:runtime.prepared_for_current_episode=result
            return result
        from unittest.mock import patch
        with patch.object(original,'CommandJournal',NativeCommandJournal), patch.object(original.DedicatedCloneManager,'prepare',prepare):
            async with super().open_case(case,out_dir) as active:
                # Preserve the original saved SQL/search readback, while also
                # retaining the full unmasked post-reload native image.
                original_saved=active.saved_state
                async def saved_state():
                    result=await original_saved()
                    from enterprise_fallback.odoo18.odoo_native_surface_evidence_v6 import EvidenceStore
                    store=EvidenceStore(out_dir)
                    result['full_native_readback_image']=store.write('saved-readback.png',await active.page.screenshot(type='png',full_page=False),'raw_observation_image')
                    result['full_native_readback_context']=store.json('saved-readback-context.private.json',await active.page.evaluate(NATIVE_JS,[]),'native_observation_envelope')
                    return result
                active.saved_state=saved_state
                yield active
