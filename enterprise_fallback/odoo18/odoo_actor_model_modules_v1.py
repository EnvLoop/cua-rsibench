"""Additive current-native Odoo actor loop clocks; legacy source stays frozen."""
from __future__ import annotations
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import time
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached,DeadlineFuture
from cursibench.native_surface_guard_policy_v1 import GuardError
from .odoo_actor_transport_v1 import sampler_class,attach_sampler_clock,deadline_sample,known_token_total

SOURCE='enterprise_fallback/odoo18/selection_worker_v066.py'


def run_owned_task(*,environment,task,index,sampler,task_dir,attempt_id):
    """One actual clean sampler/task/close; caller owns its existing paid IDs."""
    started=time.monotonic()
    with sampler as active_sampler:
        with environment.batch() as active:
            row=active.run_case(task,index,active_sampler,task_dir)
    ended=time.monotonic()
    clock=environment.actor_clock
    if ended-started>1200:raise GuardError('owned_complete_task_lifecycle_exceeded_1200')
    runtime=environment.runtime_receipt
    if not all(runtime.get(name) is True for name in ('services_restored_to_initial_state',
        'final_database_snapshot_equal','final_physical_filestore_equal')):
        raise GuardError('owned_task_batch_cleanup_unproved')
    close=getattr(sampler,'provider_close_reference',None)
    if close is None:raise GuardError('owned_task_provider_close_ack_missing')
    reference=clock.store.json('actor-clock/complete-lifecycle.private.json',{
        'schema':'odoo-owned-complete-lifecycle-v12','attempt_id':attempt_id,
        'task_id':task['task_id'],'package_sha256':task['package_sha256'],
        'started_monotonic':started,'ended_monotonic':ended,'actor_clock':clock.end_ref,
        'provider_close':close,'batch_cleanup':runtime,
        'saved_readback_reset_and_provider_close_complete':True,'owned_lease_seconds_limit':1200},
        'native_observation_envelope')
    return {**row,'owned_complete_lifecycle_ref':reference,'provider_close_ref':close}


def call_teacher_with_deadline(callback,observation,current_frame,clock):
    clock.check('before_teacher_submission')
    executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='owned-odoo-teacher')
    future=executor.submit(callback,observation,current_frame)
    try:return DeadlineFuture(future,actor_deadline=clock.deadline,clock=clock.clock).result()
    finally:executor.shutdown(wait=False,cancel_futures=False)


def save_budget_stop(adapter,error,sampler,observation):
    clock=adapter.actor_clock
    if type(error) is not ActorDeadlineReached or not error.proof.actor_deadline_reached or error.proof.actor_deadline_monotonic!=clock.deadline:
        raise GuardError('actor_budget_stop_type_or_deadline_changed')
    clock.deadline_exception=error
    value={'schema':'odoo-actor-budget-stop-v1','task_id':adapter.task_id,
        'package_sha256':adapter.task_binding_sha256,'actor_deadline_proof':error.proof.receipt(),
        'model_response_used_for_gui':False,'same_request_replay_authorized':False,'native_io_called':False,
        'observation_frame_id':None if observation is None else observation.frame_id}
    reference=clock.store.json('actor-clock/budget-stop.private.json',value,'dispatch_receipt')
    clock.budget_stop_reference=reference
    # Only an actual retained SDK request gets a sample row. A stop before a
    # new request never invents a paid ID, completed result or token count.
    if observation is not None:
        current=sampler;seen=set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            if getattr(current,'last_deadline_result',None) is not None:
                return deadline_sample(sampler,observation,error)
            current=getattr(current,'delegate',None)
    return None


_BEFORE_SAMPLE='''                    result = sampler.sample(observation, task_index=index,
                                            step=step, task_dir=task_dir)'''
_AFTER_SAMPLE='''                    attach_sampler_clock(sampler,adapter.actor_clock)
                    try:
                        result = sampler.sample(observation, task_index=index,
                                                step=step, task_dir=task_dir)
                    except ActorDeadlineReached as error:
                        last = save_budget_stop(adapter,error,sampler,observation)
                        if last is not None:samples.append(last)
                        termination="task_wall_budget"
                        break'''
_BEFORE_OBSERVE='''                    observation, rendered = adapter.observe_for_model(
                        memory=memory)'''
_AFTER_OBSERVE='''                    try:
                        observation, rendered = adapter.observe_for_model(memory=memory)
                    except ActorDeadlineReached as error:
                        save_budget_stop(adapter,error,sampler,None)
                        termination="task_wall_budget"
                        break'''

SUBSTITUTIONS=(
    ('                memory = ""','                started = adapter.started\n                self.actor_clock=adapter.actor_clock\n                memory = ""'),
    ('''                    if time.monotonic() - started > WALL_SECONDS_PER_TASK:
                        termination = "task_wall_budget"
                        break''',
     '''                    if time.monotonic() >= adapter.actor_clock.deadline:
                        try:adapter.actor_clock.check("before_next_actor_turn")
                        except ActorDeadlineReached as error:save_budget_stop(adapter,error,sampler,None)
                        termination = "task_wall_budget"
                        break'''),
    (_BEFORE_OBSERVE,_AFTER_OBSERVE),(_BEFORE_SAMPLE,_AFTER_SAMPLE),
    ('''                    try:
                        applied = adapter.dispatch(action)
                    except ContractError as exc:''',
     '''                    try:
                        applied = adapter.dispatch(action)
                    except ActorDeadlineReached as error:
                        save_budget_stop(adapter,error,sampler,observation)
                        termination="task_wall_budget"
                        break
                    except ContractError as exc:'''),
    ('                # Browser reload is evaluator-owned readback, after actor work.',
     '''                self.actor_clock.end(termination,deadline_exception=self.actor_clock.deadline_exception if termination=="task_wall_budget" else None)
                # Browser reload is evaluator-owned readback, after actor work.'''),
    ('        rendered_input = sum(row["usage"]["input_tokens"] for row in samples)',
     '        rendered_input = known_token_total(samples,"input_tokens")'),
    ('        sampled_output = sum(row["usage"]["output_tokens"] for row in samples)',
     '        sampled_output = known_token_total(samples,"output_tokens")'),
    ('                "termination": termination}\n\n',
     '                "termination": termination,"actor_clock_ref":self.actor_clock.end_ref}\n\n'),
    ('''        except Exception:
            if not any(row.get("paid_attempt_id") == paid_id for row in''',
     '''        except ActorDeadlineReached:
            raise
        except Exception:
            if not any(row.get("paid_attempt_id") == paid_id for row in'''),
)


def load(workers,binding):
    """Execute existing native substitutions plus this isolated loop delta."""
    core=workers._impl._impl;original=core._isolated_module
    def isolate(relative,tag,current,substitutions=()):
        if relative==SOURCE:
            return original(relative,tag+'_actor_clock_v1',current,substitutions+SUBSTITUTIONS)
        if relative=='enterprise_fallback/odoo18/teacher_episode_worker_v066.py':
            before='''                    sampled = sample_teacher(observation,
                                             active.current_frame_id)'''
            after='''                    sampled = call_teacher_with_deadline(sample_teacher,observation,
                                             active.current_frame_id,active.adapter.actor_clock)'''
            return original(relative,tag+'_actor_clock_v1',current,substitutions+((before,after),))
        return original(relative,tag,current,substitutions)
    core._isolated_module=isolate
    native_load=getattr(core,'_actor_native_original_model_modules',core._model_modules)
    try:teacher,selection=native_load(binding)
    finally:core._isolated_module=original
    selection.ActorDeadlineReached=ActorDeadlineReached
    selection.attach_sampler_clock=attach_sampler_clock
    selection.save_budget_stop=save_budget_stop
    selection.known_token_total=known_token_total
    teacher.call_teacher_with_deadline=call_teacher_with_deadline
    if not getattr(selection,'_actor_clock_lifecycle_installed',False):
        original_case=selection.RealOdooSelectionEnvironment.run_case
        def run_case(environment,task,index,sampler,task_dir):
            started=time.monotonic()
            row=original_case(environment,task,index,sampler,task_dir)
            ended=time.monotonic()
            if ended-started>1200:raise GuardError('owned_task_setup_readback_reset_exceeded_1200')
            clock=environment.actor_clock
            reference=clock.store.json('actor-clock/task-lifecycle.private.json',{
                'schema':'odoo-actual-task-lifecycle-v1','task_id':task['task_id'],'package_sha256':task['package_sha256'],
                'lifecycle_started_monotonic':started,'readback_and_reset_ended_monotonic':ended,
                'lifecycle_elapsed_until_case_reset_seconds':ended-started,'actor_clock':clock.end_ref,
                'provider_close_not_inferred':True,'owned_lease_seconds_limit':1200},'native_observation_envelope')
            return {**row,'task_lifecycle_ref':reference}
        selection.RealOdooSelectionEnvironment.run_case=run_case
        selection._actor_clock_lifecycle_installed=True
    if not getattr(teacher,'_actor_clock_readback_installed',False):
        original_readback=teacher._RealOdooSession.read_saved_state
        def read_saved_state(session):
            session.adapter.actor_clock.end('model_finish')
            return original_readback(session)
        teacher._RealOdooSession.read_saved_state=read_saved_state
        teacher._actor_clock_readback_installed=True
    if not getattr(selection,'_actor_clock_transport_installed',False):
        selection._actor_native_original_sampler_class=selection.RealTinkerSelectionSampler
        selection.RealTinkerSelectionSampler=sampler_class(selection)
        selection._actor_clock_transport_installed=True
    return teacher,selection
