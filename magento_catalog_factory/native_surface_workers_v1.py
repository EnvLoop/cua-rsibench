"""Source-bound original-Magento v22 teacher, selection and final interfaces."""
from __future__ import annotations
import asyncio
from hashlib import sha256
from decimal import Decimal
import json
from pathlib import Path
import time
from cursibench import full_study_runtime_v2 as v22
from cursibench import full_study_final_dispatch_v1 as final
from cursibench import full_study_matrix_v1 as matrix
from cursibench import native_surface_guard_policy_v1 as policy
from cursibench import full_study_selection_environment_v2 as environment
from . import seed,verify
from .native_surface_actor_v1 import Runtime,run_task
from .native_surface_guard_v1 import PROFILE
from enterprise_fallback.odoo18 import selection_worker_v066 as qwen
from enterprise_fallback.odoo18.odoo_actor_transport_v1 import sampler_class

ROOT=Path(__file__).resolve().parents[1]
CELL='magento-admin'
SOURCES=('magento_catalog_factory/native_surface_workers_v1.py',
 'magento_catalog_factory/native_surface_actor_v1.py','magento_catalog_factory/native_surface_guard_v1.py',
 'magento_catalog_factory/native_surface_lease_v1.py','magento_catalog_factory/seed.py',
 'magento_catalog_factory/native_surface_budget_performance_v1.py',
 'magento_catalog_factory/plan.py','magento_catalog_factory/verify.py',
 'tools/magento_dedicated_train_lane_v066.py','tools/qualify_magento_original_catalog_v1.py',
 'tools/sweep_magento_original_gui_controls_v1.py','tools/start_magento_native_sidecar_clone_v1.py',
 'tools/magento_cron_runtime_contract_v1.py','tools/reconcile_magento_unseeded_search_drift_v1.py',
 'src/cursibench/native_surface_guard_policy_v1.py','src/cursibench/scale_vision_proxy.py',
 'native_desktop_factory/actor_deadline_future_v21.py','native_desktop_factory/deadline_model_transport_v21.py',
 'enterprise_fallback/odoo18/odoo_actor_clock_v1.py','enterprise_fallback/odoo18/odoo_actor_transport_v1.py',
 'enterprise_fallback/odoo18/selection_worker_v066.py','src/cursibench/full_study_runtime_v2.py',
 'src/cursibench/full_study_final_performance_v2.py','src/cursibench/scale_action_contract.py',
 'src/cursibench/scale_action_contract_v066.py','src/cursibench/scale_action_output_v066.py',
 'src/cursibench/full_study_teacher_adapter_v1.py','src/cursibench/full_study_performance_coverage_v2.py',
 'src/cursibench/full_study_campaign_dispatch_v1.py','src/cursibench/full_study_shared_base_execution_v1.py',
 'src/cursibench/full_study_selection_environment_v2.py','src/cursibench/full_study_selection_environment_v1.py',
 'magento_catalog_factory/native_surface_shared_base_v1.py',
 'magento_catalog_factory/native_surface_teacher_v1.py','magento_catalog_factory/native_surface_facade_v1.py',
 'tools/magento_native_surface_final_v1.py')


def require(value,code):
    if not value:raise policy.GuardError(code)
def digest(raw):return sha256(raw).hexdigest()
def private_json(path,expected=None):
    path=Path(path);require(path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0,
        'magento_private_file_unsafe')
    raw=path.read_bytes();require(expected is None or digest(raw)==expected,'magento_private_file_changed')
    value=json.loads(raw);require(type(value) is dict,'magento_private_object_required');return value
def write(root,name,value):
    path=Path(root)/name;final.private_write_new(path,final.canonical(value));return final.reference(root,path)


def public_binding():
    value={'schema':'magento-native-five-slot-source-binding-v1','profile':PROFILE,'policy_sha256':policy.POLICY_SHA,
        'all_teacher_control_base_and_four_checkpoint_slots_same_source':True,'max_actions':90,'actor_seconds':720,
        'owned_lifecycle_seconds':1200,'environment_category':environment.category(CELL),
        'native_environment':environment.NATIVE_BY_CELL[CELL],'environment_policy_sha256':environment.binding_sha256(),'original_sql_search_scorer_and_fresh_clone_reset':True,
        'whole_raster_equality_required':False,'old_control_credit':0,
        'source_sha256s':{name:digest((ROOT/name).read_bytes()) for name in SOURCES}}
    return {**value,'binding_sha256':digest(final.canonical(value))}


def verify_environment_scope(study):
    require(environment.category(CELL)=='storage_application' and
        environment.NATIVE_BY_CELL[CELL]=='owned_self_hosted_original_application' and
        study.amendment['effective_environment_categories'][CELL]=='storage_application' and
        study.amendment['native_environment_by_cell'][CELL]=='owned_self_hosted_original_application' and
        study.amendment['environment_policy_sha256']==environment.binding_sha256(),
        'magento_original_local_app_search_environment_not_ratified')


def study_source_snapshot():
    binding=public_binding()
    return {'schema':'magento-native-surface-study-source-snapshot-v1','native_worker_binding_sha256':binding['binding_sha256'],
        'source_sha256s':binding['source_sha256s']}


class Inputs:
    """Metadata-only constructor; task bodies are opened by load after gates."""
    def __init__(self,*,plan_path,plan_sha256,binding_path,binding_sha256,lane_path,lane_sha256,output_root,control_preparation_only=False):
        self.control_preparation_only=control_preparation_only
        self.plan_path=Path(plan_path);self.plan_sha=plan_sha256;self.binding_path=Path(binding_path);self.binding_sha=binding_sha256
        self.lane_path=Path(lane_path);self.lane_sha=lane_sha256;self.output=Path(output_root).resolve()
        self.binding=private_json(self.binding_path,binding_sha256)
        require(self.binding==public_binding(),'magento_five_slot_source_binding_changed')
        self.lane=private_json(self.lane_path,lane_sha256)
        require(self.lane.get('schema')=='magento-native-owned-lane-admission-v1' and
            self.lane.get('source_binding_sha256')==self.binding['binding_sha256'] and
            (control_preparation_only or self.lane.get('native_train_positive_negative_reset_reviewed') is True) and
            type(self.lane.get('source_search_sha256')) is str and len(self.lane['source_search_sha256'])==64,
            'magento_fresh_owned_lane_admission_required')
        self.roster=private_json(self.lane['roster_metadata_ref']['path'],self.lane['roster_metadata_ref']['sha256'])
        require(set(self.roster)=={'schema','plan_sha256','splits'} and self.roster['schema']=='magento-native-roster-metadata-v1'
            and self.roster['plan_sha256']==plan_sha256 and set(self.roster['splits'])=={'train','selection','official_candidate'}
            and all(len(self.roster['splits'][key])==count for key,count in [('train',20),('selection',20),('official_candidate',100)]),
            'magento_exact_twenty_twenty_hundred_metadata_required')
        ids=[row['task_id'] for rows in self.roster['splits'].values() for row in rows]
        require(len(ids)==len(set(ids)),'magento_split_overlap')
        if not control_preparation_only:self.validate_train_admission()

    def validate_train_admission(self):
        from .native_surface_budget_performance_v1 import audit_episode
        control_ref=self.lane.get('native_train_controls_ref');review_ref=self.lane.get('root_source_visual_review_ref')
        require(type(control_ref) is dict and type(review_ref) is dict,'magento_fresh_native_train_evidence_required')
        control=private_json(control_ref['path'],control_ref['sha256']);review=private_json(review_ref['path'],review_ref['sha256'])
        require(control['schema']=='magento-native-surface-control-set-v1' and control['source_binding_sha256']==self.binding['binding_sha256'] and
            control['split']=='train' and control['task_count']==1 and len(control['tasks'])==1 and control['model_calls']==0 and
            control['formal_registration_performed'] is False and control['old_development_control_credit']==0,
            'magento_new_native_train_control_epoch_required')
        identity={k:control['tasks'][0][k] for k in ('task_id','package_sha256')}
        require(identity in self.roster['splits']['train'],'magento_train_control_outside_current_train')
        source_images=[]
        for mode,expected in [('baseline',0),('positive',1),('wrong_variant',0)]:
            proof=control['tasks'][0]['trio'][mode];folder=Path(proof['episode_root'])
            row=private_json(folder/'native-row.private.json',proof['native_row_sha256'])
            audited=audit_episode(folder,row,provider_close_required=False)
            require(row['score']==proof['score']==expected and {k:row[k] for k in identity}==identity,
                'magento_actual_train_trio_rederivation_failed')
            source_images.append(audited['frames'][0]['frame']['sha256'])
        require(review.get('schema')=='magento-root-native-source-visual-review-v1' and
            review.get('source_binding_sha256')==self.binding['binding_sha256'] and review.get('task_id')==identity['task_id'] and
            review.get('reviewed_source_frame_sha256s')==source_images and review.get('original_source_readable') is True and
            review.get('no_masked_answer_pixels') is True,'magento_root_actual_source_review_required')

    def load(self,identity,split):
        require(identity in self.roster['splits'][split],'magento_task_outside_frozen_roster')
        case=seed.load_case(self.plan_path,self.plan_sha,identity['task_id'])
        require(case['package_sha256']==identity['package_sha256'] and case['split']==split,'magento_case_package_or_split_changed')
        return case

    def runtime(self):
        return Runtime(self.lane,self.lane_path)

    def username(self):
        ref=self.lane['actor_credentials_ref'];value=private_json(ref['path'],ref['sha256'])
        require(type(value.get('username')) is str and value['username'],'magento_actor_username_missing')
        return value['username']


def execute_owned(inputs,identity,split,output,*,attempt_id,paid_attempt_id,checkpoint_path,checkpoint_sha256,config):
    """Gate caller owns paid intent; one fresh real Qwen session per task."""
    case=inputs.load(identity,split)
    cls=sampler_class(qwen)
    base=checkpoint_path is None
    sampler=cls(checkpoint_path='Qwen/Qwen3.8-27B' if base else checkpoint_path,config=config,
        output_root=Path(output),attempt_id=attempt_id,base_mode=base,
        expected_base_checkpoint_sha256=checkpoint_sha256 if base else None)
    started_at=int(time.time());started=time.monotonic()
    with sampler as active:
        row=asyncio.run(run_task(case=case,task=identity,output=output,runtime=inputs.runtime(),sampler=active,
            username=inputs.username(),attempt_id=attempt_id,paid_attempt_id=paid_attempt_id))
    ended=time.monotonic();require(ended-started<=1200,'magento_setup_reset_close_lifecycle_exceeded_1200')
    close=getattr(sampler,'provider_close_reference',None);require(close is not None,'magento_owned_provider_close_missing')
    row={**row,'complete_lifecycle_wall_time_ms':round((ended-started)*1000),'provider_close_ref':close}
    row.update(started_at=started_at,finished_at=int(time.time()))
    write(output,'native-row.private.json',row);return row


class PaidSampler:
    def __init__(self,delegate,dispatch_paid,attempt_id,identity):
        self.delegate=delegate;self.dispatch_paid=dispatch_paid;self.attempt_id=attempt_id;self.identity=identity;self.ids=[]
        self.checkpoint_sha256=None;self.common={}
    def __enter__(self):self.delegate.__enter__();return self
    def __exit__(self,*args):return self.delegate.__exit__(*args)
    def __getattr__(self,name):return getattr(self.delegate,name)
    def next_paid_attempt_id(self,step):return self.attempt_id+f'-sample-{step:03d}'
    def sample(self,observation,**kwargs):
        self.delegate.actor_clock=self.actor_clock
        identifier=self.next_paid_attempt_id(observation.step)
        self.ids.append(identifier)
        request={**self.common,'schema':'magento-current-frame-paid-request-v1','task_id':observation.task_id,
            'package_sha256':observation.task_binding_sha256,'checkpoint_path_sha256':self.checkpoint_sha256,'frame_id':observation.frame_id,
            'frame_sha256':observation.screenshot['sha256'],'step':observation.step}
        def provider(actual):
            require(actual==request,'magento_paid_frame_request_changed')
            return self.delegate.sample(observation,**kwargs)
        paid=self.dispatch_paid(attempt_id=identifier,category='tinker',work=request,request=request,
            reserve_usd='1',resource_reservation={},provider=provider)
        require(paid['attempt_id']==identifier,'magento_paid_sample_identity_changed')
        return {**paid['result'],'paid_attempt_id':identifier}


class SelectionWorker:
    """Exact current start-selection task set; one source for base and CP."""
    cell_id=CELL
    def __init__(self,*,study,inputs,enable_live=False):
        require(type(study) is v22.FrozenStudy,'real_v22_frozen_study_required')
        verify_environment_scope(study)
        self.study=study;self.inputs=inputs;self.enable_live=enable_live
        require(not inputs.control_preparation_only,'native_train_admission_required_before_model')
        inputs.validate_train_admission()
        self.runtime_sha256=inputs.binding['binding_sha256']
        self.verifier_sha256=inputs.binding['source_sha256s']['magento_catalog_factory/verify.py']
        cell=next(r for r in study.plan['cells'] if r['cell_id']==CELL)
        require(cell['matched_bindings']['runtime']==self.runtime_sha256 and
            cell['matched_bindings']['source_snapshot']==digest(final.canonical(study_source_snapshot())) and
            cell['matched_bindings']['verifier']==self.verifier_sha256,'magento_selection_source_not_ratified')

    def run_selection(self,*,started,checkpoint_path,student_config_raw,student_config_sha256,out_dir,dispatch_paid,base_mode=False):
        require(self.enable_live,'magento_explicit_live_required')
        require(self.inputs.binding==public_binding(),'magento_source_changed_after_constructor')
        self.inputs.validate_train_admission()
        session=getattr(dispatch_paid,'__self__',None)
        require(session is not None and session.study is self.study and session.cell_id==CELL if hasattr(session,'cell_id') else
            session is not None and session.study is self.study and session.intent['cell_id']==CELL,'magento_actual_owned_paid_session_required')
        owner=session.intent['researcher_id']
        require(digest(student_config_raw)==student_config_sha256,'magento_training_configuration_changed')
        frozen_config,frozen_sha=self.study.student_training_configuration()
        require(student_config_sha256==frozen_sha and json.loads(student_config_raw)==frozen_config,'magento_not_frozen_training_configuration')
        config=json.loads(student_config_raw);tasks=[{k:r[k] for k in ('task_id','package_sha256')} for r in started['selection_tasks']]
        require(tasks==self.inputs.roster['splits']['selection'] and len(tasks)==20 and started['task_count']==20,'magento_exact_twenty_selection_required')
        if base_mode:
            require(started==session.started,'magento_actual_shared_base_start_required')
            cell=next(r for r in self.study.plan['cells'] if r['cell_id']==CELL)
            require(owner=='shared-base' and checkpoint_path=='Qwen/Qwen3.8-27B' and
                started['checkpoint_path_sha256']==cell['base_checkpoint_sha256'],'magento_base_model_changed')
        else:
            starts=[r for r in session._events('selection_started') if r['data']['attempt_id']==started['attempt_id']]
            require(len(starts)==1 and all(starts[0]['data'][k]==started[k] for k in ('attempt_id','checkpoint_path_sha256','selection_identities_sha256','task_count')) and
                started['selection_tasks']==session.views['selection'],'magento_actual_selection_start_required')
            require(owner in matrix.RESEARCHERS and final.SAMPLER_PATH.fullmatch(checkpoint_path) and digest(checkpoint_path.encode())==started['checkpoint_path_sha256'],
                'magento_selected_checkpoint_not_actual_path')
            checkpoints=[r for r in session._events('tinker_checkpoint') if r['data']['checkpoint_path_sha256']==started['checkpoint_path_sha256']]
            require(len(checkpoints)==1 and session.checkpoint_result(checkpoints[0])['checkpoint_path']==checkpoint_path,'magento_actual_paid_checkpoint_lineage_required')
        output=Path(out_dir).absolute()
        require(not output.exists() and not output.is_symlink() and output.parent.resolve().is_relative_to(self.study.repo_root/'work'),
            'magento_fresh_owned_selection_output_required')
        output.mkdir(mode=0o700,parents=True)
        rows=[];paid_ids=[];coverage_calls=[];budget_receipts=[]
        checkpoint=started['checkpoint_path_sha256']
        for index,identity in enumerate(tasks):
            task_dir=output/f'task-{index:03d}';task_dir.mkdir(mode=0o700)
            identifier=started['attempt_id']+f'-task-{index:03d}'
            common={'cell_id':CELL,'selection_attempt':started['attempt_id'],'task_id':identity['task_id'],
                'package_sha256':identity['package_sha256'],'checkpoint_path_sha256':checkpoint}
            request={**common,'schema':'magento-native-v22-paid-task-v1','native_source_binding_sha256':self.runtime_sha256,
                'max_actions':90,'actor_seconds':720,'lifecycle_seconds':1200}
            actual_calls=[]
            def tracked_dispatch(**kwargs):
                req=kwargs['request'];ident=kwargs['attempt_id'];kind=kwargs['category']
                try:paid=dispatch_paid(**kwargs)
                except BaseException:
                    actual_calls.append({'attempt_id':ident,'category':kind,'request':req,'result_present':False,'result_status':None})
                    raise
                actual_calls.append({'attempt_id':ident,'category':kind,'request':req,'result_present':True,'result_status':paid['result'].get('status')})
                return paid
            def provider(actual_request):
                require(actual_request==request,'magento_paid_task_request_changed')
                case=self.inputs.load(identity,'selection');cls=sampler_class(qwen)
                real=cls(checkpoint_path='Qwen/Qwen3.8-27B' if base_mode else checkpoint_path,config=config,
                    output_root=task_dir,attempt_id=identifier,base_mode=base_mode,
                    expected_base_checkpoint_sha256=checkpoint if base_mode else None)
                wrapped=PaidSampler(real,tracked_dispatch,identifier,identity);wrapped.checkpoint_sha256=checkpoint;wrapped.common=common
                began=time.monotonic();setup_id=identifier+'-sampler-setup'
                setup_request={**common,'task_id':None,'package_sha256':None,'checkpoint_path_sha256':checkpoint,'schema':'magento-owned-sampler-setup-v1'}
                tracked_dispatch(attempt_id=setup_id,category='tinker',work=setup_request,request=setup_request,
                    reserve_usd='1',resource_reservation={},provider=lambda _: (wrapped.__enter__(),{'status':'completed','actual_owned_sampler_started':True})[1])
                try:
                    row=asyncio.run(run_task(case=case,task=identity,output=task_dir,runtime=self.inputs.runtime(),
                        sampler=wrapped,username=self.inputs.username(),attempt_id=identifier,paid_attempt_id=identifier))
                finally:wrapped.__exit__(None,None,None)
                ended=time.monotonic();require(ended-began<=1200,'magento_owned_selection_lifecycle_exceeded_1200')
                row={**row,'complete_lifecycle_wall_time_ms':round((ended-began)*1000),
                    'provider_close_ref':real.provider_close_reference,'actual_sample_paid_attempt_ids':wrapped.ids}
                write(task_dir,'native-row.private.json',row)
                return {'schema':'magento-native-v22-paid-performance-v1','status':'completed','task_id':identity['task_id'],
                    'package_sha256':identity['package_sha256'],'native_row':final.reference(output,task_dir/'native-row.private.json'),
                    'score':row['score'],'usage':{'provider_billed_tokens':None},'actual_billing_unknown':True}
            tracked_dispatch(attempt_id=identifier,category='storage_application',work=request,request=request,
                reserve_usd='1',resource_reservation={},provider=provider)
            row=private_json(task_dir/'native-row.private.json')
            from .native_surface_budget_performance_v1 import audit_episode,prepare_budget_performance
            audited=audit_episode(task_dir,row)
            if any(r['status']=='actor_deadline_proven' for r in row['samples']):
                stopped=next(r for r in row['samples'] if r['status']=='actor_deadline_proven')
                command={**identity,'attempt_id':identifier,'owner_slot':owner,'checkpoint_sha256':checkpoint}
                proof=prepare_budget_performance(command=command,output=output,episode=task_dir,row=row,
                    sample_paid_attempt_id=stopped['paid_attempt_id'],prefix=f'budget-{index:03d}')
                receipt=v22.verify_budget_artifacts(self.study,owner,proof['verification'])
                session.authorize_verified_budget_stop(receipt['sample_paid_attempt_id'],verification=proof['verification'])
                budget_receipts.append(receipt)
            result_row={**identity,'score':row['score'],
                'saved_state_sha256':digest((task_dir/'saved-state.private.json').read_bytes()),
                'verifier_receipt_sha256':digest((task_dir/'verifier.private.json').read_bytes()),
                'reset_receipt_sha256':digest((task_dir/'reset.private.json').read_bytes())}
            rows.append(result_row);coverage_calls.extend(actual_calls);paid_ids.extend(r['attempt_id'] for r in actual_calls)
        from cursibench import full_study_performance_coverage_v2 as coverage
        checked=coverage.validate(plan=self.study.parent.plan,amendment=self.study.amendment,cell_id=CELL,owner_slot=owner,
            attempt_id=started['attempt_id'],checkpoint_sha256=checkpoint,selection_tasks=tasks,paid_calls=coverage_calls,
            related_paid_attempt_ids=set(paid_ids),budget_performance_receipts=budget_receipts)
        result={'schema':'cua-full-study-selection-saved-result-v1','cell_id':CELL,'checkpoint_sha256':checkpoint,
            'evaluator_isolated':True,'tasks':rows}
        result_ref=write(output,'selection-result.private.json',result)
        ledger_ref=write(output,'task-ledger.private.json',{'schema':'magento-native-selection-performance-ledger-v1',
            'tasks':rows,'paid_attempt_ids':paid_ids,'coverage':checked,'amendment_sha256':self.study.amendment_sha256,
            'source_binding_sha256':self.runtime_sha256,'episode_dirs':[f'task-{i:03d}' for i in range(20)]})
        return {'status':'scored','result':result,'result_sha256':result_ref['sha256'],'paid_attempt_ids':paid_ids,
            'task_ledger_path':str(output/'task-ledger.private.json'),'task_ledger_sha256':ledger_ref['sha256'],
            'performance_coverage':checked,'actual_cost_usd':None,'invoice_complete':False}


def selection_worker_factory(*,study,inputs=None,inputs_path=None,inputs_sha256=None,enable_live=False):
    require((inputs is None)!=(inputs_path is None),'one_source_bound_input_form_required')
    if inputs is None:inputs=Inputs(**private_json(inputs_path,inputs_sha256))
    return SelectionWorker(study=study,inputs=inputs,enable_live=enable_live)


def run_shared_base(study,*,inputs,output,enable_live=False,usage_reconciler=lambda *_:None):
    require(type(study) is v22.FrozenStudy,'real_v22_frozen_study_required')
    session=v22.SharedBaseSession(study,CELL);started=session.started
    config,config_sha=study.student_training_configuration();raw=final.canonical(config)
    require(digest(raw)==config_sha,'magento_shared_base_training_bytes_changed')
    worker=SelectionWorker(study=study,inputs=inputs,enable_live=enable_live)
    result=worker.run_selection(started=started,checkpoint_path='Qwen/Qwen3.8-27B',student_config_raw=raw,
        student_config_sha256=config_sha,out_dir=output,dispatch_paid=session.dispatch_paid,base_mode=True)
    from .native_surface_shared_base_v1 import admit_shared_base
    return admit_shared_base(study=study,inputs=inputs,session=session,native_result=result,usage_reconciler=usage_reconciler)


class FinalWorker:
    def __init__(self,*,gate,inputs,enable_live=False):
        require(type(gate) is v22.FinalGate,'real_v22_final_gate_required')
        verify_environment_scope(gate.study)
        self.gate=gate;self.inputs=inputs;self.enable_live=enable_live
        require(not inputs.control_preparation_only,'native_train_admission_required_before_final')
        inputs.validate_train_admission()
        require(inputs.output.parent.resolve().is_relative_to((gate.study.repo_root/'work').resolve()),'magento_final_output_outside_private_work')
        self.cell=next(row for row in gate.plan['cells'] if row['cell_id']==CELL)
        require(self.cell['matched_bindings']['runtime']==inputs.binding['binding_sha256'] and
            self.cell['matched_bindings']['source_snapshot']==digest(final.canonical(study_source_snapshot())),
            'magento_final_runtime_not_frozen')
        self.identities=[r for chunk in self.cell['base']['chunks'] for r in chunk['tasks']]
        require(self.identities==inputs.roster['splits']['official_candidate'],'magento_full_hundred_sealed_metadata_changed')
        slots=[self.cell['base'],*self.cell['researcher_plans'].values()]
        require(len(slots)==5 and all(all(slot['bindings'][k]==self.cell['matched_bindings'][k] for k in
            ('source_snapshot','runtime','action_contract','verifier')) for slot in slots),'magento_final_five_slot_bindings_differ')
        b=self.cell['matched_bindings']
        self._identity={'schema':final.WORKER_SCHEMA,'cell_id':CELL,'source_snapshot_sha256':b['source_snapshot'],
            'runtime_sha256':b['runtime'],'action_contract_sha256':b['action_contract'],'verifier_sha256':b['verifier'],
            'adapter_source_sha256':inputs.binding['source_sha256s']['magento_catalog_factory/native_surface_guard_v1.py'],
            'action_profile':'scale-action-profile-v0.6.6','observation_kind':'screenshot','actor_capability':'current_frame_gui_actions_only',
            'evaluator_isolated':True,'cold_reset_supported':True,'saved_state_readback_supported':True}
        final._worker_identity(self,self.cell,gate.frozen.ratification)
    @property
    def identity(self):return dict(self._identity)
    def run_once(self,command,output_dir):
        require(self.enable_live,'magento_explicit_live_required')
        require(self.inputs.binding==public_binding(),'magento_source_changed_after_final_constructor')
        self.inputs.validate_train_admission()
        fields={'schema','study_id','cell_id','owner_slot','task_id','package_sha256','checkpoint_sha256','sampler_path',
            'expected_initial_state_sha256','attempt_id','retry_index','retry_rule_sha256','action_profile','sampling',
            'max_actions','max_wall_seconds','matched_bindings','reserve_usd'}
        require(type(command) is dict and set(command)==fields and command['schema']==final.COMMAND_SCHEMA and
            command['cell_id']==CELL and command['study_id']==self.gate.plan['study_id'] and
            command['matched_bindings']==self.cell['matched_bindings'],'magento_final_command_scope_changed')
        identity={k:command[k] for k in ('task_id','package_sha256')};require(identity in self.identities,'magento_final_task_not_sealed')
        owner=command['owner_slot'];require(owner in self.cell['execution_evidence_owner_by_slot'].values(),'magento_final_owner_changed')
        slot=self.cell['base'] if owner=='shared-base' else self.cell['researcher_plans'][owner]
        ordinal=self.identities.index(identity);retry=command['retry_index']
        require(type(retry) is int and retry in (0,1) and command['attempt_id']==f'final-{matrix.CELLS.index(CELL):02d}-{owner}-{ordinal:03d}-{retry}' and
            command['retry_rule_sha256']==(final.RETRY_RULE_SHA256 if retry else None) and
            command['checkpoint_sha256']==slot['bindings']['checkpoint'] and command['sampling']==slot['sampling'] and
            command['max_actions']==slot['execution']['max_actions_per_task']==90 and
            command['max_wall_seconds']==slot['execution']['max_wall_seconds_per_task']==720 and
            command['expected_initial_state_sha256']==self.gate.initial_state_by_task[CELL][command['task_id']] and
            command['action_profile']=='scale-action-profile-v0.6.6','magento_final_checkpoint_policy_changed')
        require((owner=='shared-base' and command['sampler_path'] is None) or
            (owner!='shared-base' and type(command['sampler_path']) is str and final.SAMPLER_PATH.fullmatch(command['sampler_path']) and
             digest(command['sampler_path'].encode())==command['checkpoint_sha256']),'magento_final_checkpoint_path_unbound')
        reservation=self.gate.budget.owner_attempts(CELL+':'+owner).get(command['attempt_id'])
        require(type(reservation) is dict and reservation['status']=='dispatched' and
            reservation['category']==('shared_base_final' if owner=='shared-base' else 'selected_final') and
            reservation['request_sha256']==digest(final.canonical(command)) and
            Decimal(reservation['reserved_usd'])==Decimal(command['reserve_usd']),'magento_final_actual_paid_reservation_required')
        output=Path(output_dir);require(output.name==command['attempt_id'] and output.parent.resolve()==self.inputs.output and
            output.is_dir() and not output.is_symlink() and output.stat().st_mode&0o077==0,'magento_owned_final_output_required')
        write(output,'worker-intent.private.json',{'command':command,'source_binding_sha256':self.inputs.binding['binding_sha256'],
            'same_request_replay_authorized':False})
        config,_=self.gate.study.student_training_configuration()
        config={**config,'seed':command['sampling']['seed'],'sample_max_tokens':command['sampling']['max_output_tokens']}
        episode=output/'native-episode';episode.mkdir(mode=0o700)
        row=execute_owned(self.inputs,identity,'official_candidate',episode,attempt_id=command['attempt_id'],
            paid_attempt_id=command['attempt_id'],checkpoint_path=command['sampler_path'],
            checkpoint_sha256=command['checkpoint_sha256'],config=config)
        return final_outcome(command,output,episode,row,study=self.gate.study)


def final_worker_factory(*,gate,inputs=None,inputs_path=None,inputs_sha256=None,enable_live=False):
    require((inputs is None)!=(inputs_path is None),'one_source_bound_input_form_required')
    if inputs is None:inputs=Inputs(**private_json(inputs_path,inputs_sha256))
    return FinalWorker(gate=gate,inputs=inputs,enable_live=enable_live)


def final_outcome(command,output,episode,row,*,study=None):
    from .native_surface_budget_performance_v1 import audit_episode
    audit_episode(episode,row)
    saved_path=episode/'saved-state.private.json';verifier=private_json(episode/'verifier.private.json')
    saved=private_json(saved_path);reset=private_json(episode/'reset.private.json')
    independent=verify.score_saved_state(verifier['case'],verifier['baseline'],saved['snapshot'])
    require(independent==verifier['verdict'] and row['score']==int(independent['score']==1.0),
        'magento_saved_score_changed_after_readback')
    verify.check_material_reset(verifier['baseline'],reset['restored_snapshot'])
    actor=private_json(episode/'actor-clock/end.private.json')
    close=private_json(episode/row['provider_close_ref']['path'])
    require(close['status']=='acknowledged' and close['real_close_call_returned'] is True,'magento_actual_provider_close_unproved')
    samples=private_json(episode/'samples.private.json')['samples']
    def total(key):
        values=[r['raw_result'].get('usage',{}).get(key) for r in samples]
        return None if any(type(v) is not int for v in values) else sum(values)
    calls=[{'request_id':r['request_id'],'paid_attempt_id':r['paid_attempt_id'],'kind':'sample',
        'intent':{'path':'native-episode/'+r['intent']['path'],'sha256':r['intent']['sha256']},
        'result':None if r['result'] is None else {'path':'native-episode/'+r['result']['path'],'sha256':r['result']['sha256']}} for r in samples]
    usage=write(output,'usage.private.json',{'schema':'cua-full-study-authentic-unknown-usage-v2',
        'attempt_id':command['attempt_id'],'cost_basis':'authentic_usage_unknown','cost_usd':None,
        'input_tokens':total('input_tokens'),'image_tokens':total('image_tokens'),'output_tokens':total('output_tokens'),
        'provider_billed_tokens':None,'provider_invoice_sha256':None,'paid_calls':calls})
    expected=command['expected_initial_state_sha256']
    require(expected==verify.canonical_sha(verifier['baseline']),'magento_qualified_initial_state_projection_changed')
    reset_ref=write(output,'cold-reset.private.json',{'schema':final.RESET_SCHEMA,'task_id':command['task_id'],
        'package_sha256':command['package_sha256'],'attempt_id':command['attempt_id'],'fresh_environment':True,
        'restored_after_attempt':True,'initial_state_sha256':expected,'restored_state_sha256':expected})
    saved_ref=final.reference(output,saved_path)
    verifier_ref=write(output,'independent-verifier.private.json',{'schema':final.VERIFIER_SCHEMA,
        'task_id':command['task_id'],'package_sha256':command['package_sha256'],'attempt_id':command['attempt_id'],
        'saved_state_sha256':saved_ref['sha256'],'score':row['score'],'no_regression_checked':True,
        'no_regression_passed':independent['passed'],'independent_of_actor':True,'gold_withheld_from_actor':True})
    observe_ref=write(output,'observations.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':command['attempt_id'],
        'kind':'observations','action_profile':'scale-action-profile-v0.6.6','count':row['turn_count'],'screenshot_only':True})
    action_ref=write(output,'actions.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':command['attempt_id'],
        'kind':'actions','action_profile':'scale-action-profile-v0.6.6','count':row['action_count'],'current_frame_validated':True})
    clock_ref=write(output,'actor-clock.private.json',{'schema':'cua-full-study-final-actor-clock-v2','attempt_id':command['attempt_id'],
        'max_actions':90,'actor_seconds_limit':720,'lease_seconds_limit':1200,'actor_wall_time_ms':row['actor_wall_time_ms'],
        'lifecycle_wall_time_ms':row['complete_lifecycle_wall_time_ms'],'native_actions_after_deadline':0,'evaluation_outside_actor_clock':True,
        'raw_actor_clock':final.reference(output,episode/'actor-clock/end.private.json')})
    budget=None
    if any(r['status']=='actor_deadline_proven' for r in samples):
        from .native_surface_budget_performance_v1 import prepare_budget_performance
        require(study is not None,'magento_real_budget_performance_study_required')
        budget=prepare_budget_performance(command=command,output=output,episode=episode,row=row,study=study)
    return {'schema':final.OUTCOME_SCHEMA,'status':'scored','score':row['score'],'failure_type':None,
        'started_at':row['started_at'],'finished_at':row['finished_at'],'cost_basis':'authentic_usage_unknown','cost_usd':None,
        'usage':usage,'reset':reset_ref,'saved_state':saved_ref,'verifier':verifier_ref,'observation_trace':observe_ref,
        'action_trace':action_ref,'action_count':row['action_count'],'turn_count':row['turn_count'],
        'wall_time_ms':row['actor_wall_time_ms'],'provider_latency_ms':row['provider_latency_ms'],'timeout_subtype':'actor_wall_budget' if row['termination']=='task_wall_budget' else
            'actor_action_budget' if row['termination']=='task_action_budget' else 'none','action_profile':'scale-action-profile-v0.6.6',
        'actor_clock':clock_ref,'lifecycle_wall_time_ms':row['complete_lifecycle_wall_time_ms'],'budget_performance':budget}
