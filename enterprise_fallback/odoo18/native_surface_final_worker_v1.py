"""Concrete sealed Odoo final execution under the existing FinalController."""
from __future__ import annotations
from decimal import Decimal
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace
from cursibench import full_study_final_dispatch_v1 as final
from cursibench import full_study_matrix_v1 as matrix
from cursibench import full_study_qwen_runtime_gate_v1 as runtime_gate
from cursibench import native_surface_guard_policy_v1 as surface_policy

ROOT=Path(__file__).resolve().parents[2]
CELL='odoo-community'
FIELDS={'schema','study_id','cell_id','owner_slot','task_id','package_sha256','checkpoint_sha256','sampler_path',
 'expected_initial_state_sha256','attempt_id','retry_index','retry_rule_sha256','action_profile','sampling',
 'max_actions','max_wall_seconds','matched_bindings','reserve_usd'}


class OdooFinalWorkerError(ValueError):pass
def require(value,code):
    if not value:raise OdooFinalWorkerError(code)
def digest(raw):return sha256(raw).hexdigest()
def private(path):
    path=Path(path);require(path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0 and
        0<path.stat().st_size<=final.MAX_PRIVATE_BYTES,
        'final_private_file_unsafe');return path.read_bytes()
def write(root,name,value):
    path=Path(root)/name;final.private_write_new(path,final.canonical(value));return final.reference(root,path)


def _worker_module(name):
    match=re.fullmatch(r'enterprise_fallback\.odoo18\.native_surface_workers_v([1-9][0-9]*)',str(name))
    require(match is not None and int(match[1])>=8,'final_unregistered_native_worker_module')
    module=importlib.import_module(name)
    require(Path(module.__file__).resolve()==ROOT/Path(*name.split('.')).with_suffix('.py'),
        'final_native_worker_module_identity_changed')
    public=module.public_binding();module.validate_binding(public)
    require(module_from_binding(public)==name and public['native_surface_policy_sha256']==surface_policy.POLICY_SHA,
        'final_common_surface_policy_changed')
    return module


def module_from_binding(binding,explicit=None):
    require(type(binding) is dict,'final_native_binding_object_required')
    match=re.fullmatch(r'native-owned-surface-safety-envelope-v([1-9][0-9]*)',str(binding.get('profile')))
    require(match is not None and int(match[1])>=8,'final_native_binding_profile_unregistered')
    name='enterprise_fallback.odoo18.native_surface_workers_v'+match[1]
    require(explicit is None or explicit==name,'final_explicit_native_module_mismatched')
    return name


def source_binding(native_worker_module):
    current=_worker_module(native_worker_module);base=current.public_binding()
    names=('enterprise_fallback/odoo18/native_surface_final_worker_v1.py',
        'enterprise_fallback/odoo18/native_surface_shared_base_v1.py',
        'tools/odoo_native_surface_final_v1.py',
        'enterprise_fallback/odoo18/hidden_factory.py','enterprise_fallback/odoo18/multifamily.py')
    extra={name:digest((ROOT/name).read_bytes()) for name in names}
    value={'schema':'odoo-native-surface-final-source-binding-v1','native_worker_binding_sha256':base['binding_sha256'],
        'native_worker_module':native_worker_module,
        'native_surface_policy_sha256':base['native_surface_policy_sha256'],'source_sha256s':extra,
        'all_five_final_slots_same_source':True,'hidden_bodies_open_only_after_command':True}
    return {**value,'binding_sha256':digest(final.canonical(value))}


def study_source_snapshot(native_worker_module):
    """Freeze supplemental final code before campaigns in all five slots."""
    native=_worker_module(native_worker_module).public_binding();supplement=source_binding(native_worker_module)
    return {'schema':'odoo-native-surface-study-source-snapshot-v1',
        'native_worker_binding_sha256':native['binding_sha256'],
        'final_source_binding_sha256':supplement['binding_sha256'],
        'source_sha256s':{**native['source_sha256s'],**supplement['source_sha256s']}}


def _modules(worker,binding):
    code=ROOT/'enterprise_fallback/odoo18';os.environ['ENVLOOP_ODOO_WORKER_DIR']=str(worker)
    if str(code) not in sys.path:sys.path.insert(0,str(code))
    result=[]
    for name in ('factory','gui_controls','reset','verify','worker_lease'):
        loaded=sys.modules.get(name)
        require(loaded is None or Path(loaded.__file__).resolve()==code/(name+'.py'),'final_odoo_module_identity_conflict')
        module=importlib.import_module(name);result.append(module)
    factory,gui,reset,verify,lease=result
    require(worker.name=='official_hidden' and factory.HERE==worker and factory.PRIVATE==worker/'private' and
        reset.HERE==worker and verify.PRIVATE==factory.PRIVATE and gui.PRIVATE==factory.PRIVATE and lease.PRIVATE==factory.PRIVATE and
        (worker/'.env').is_file() and not (worker/'.env').is_symlink() and (worker/'.env').stat().st_mode&0o077==0 and
        (worker/'compose.yaml').is_file() and not (worker/'compose.yaml').is_symlink() and
        digest((worker/'compose.yaml').read_bytes())==binding['source_sha256s']['enterprise_fallback/odoo18/compose.yaml'] and
        factory.local_config().get('ODOO_PARTITION')=='official_hidden','final_original_worker_not_bound')
    return result


def _evaluate(family,case_id,target,baseline,observed,physical,frozen,paths,verify):
    functions={'purchase':verify.evaluate,'inventory':verify.evaluate_replenishment,
        'sales':verify.evaluate_sales,'crm':verify.evaluate_crm}
    require(family in functions,'final_family_unknown')
    result=functions[family](case_id,target,baseline,observed)
    extra=verify.protected_source_file_differences(baseline,frozen,physical)+verify.protected_source_store_path_differences(baseline,paths)
    if extra:result={**result,'reward':0.0,'checks_passed':False,'difference_codes':sorted(set(result['difference_codes']+extra))}
    return {**result,'protected_source_files_checked':len({row['checksum'] for row in baseline['attachments']})}


def environment_factory(selection,worker,identities,binding):
    """Keep the current v8 GUI loop; adapt only the sealed final partition."""
    class Environment(selection.RealOdooSelectionEnvironment):
        def _module_boundary(self):
            modules=_modules(self.worker_dir,binding)
            return modules[0],modules[1],modules[2],self.verifier_proxy if hasattr(self,'verifier_proxy') else modules[3],modules[4]

        def load_command_task(self,identity,output):
            factory,_,reset,verify,_=_modules(self.worker_dir,binding)
            manifest=json.loads(private(factory.PRIVATE/'task_set_manifest.json'))
            rows=manifest.get('official');require(type(rows) is list and len(rows)==100 and
                {r['task_id']:r['package_sha256'] for r in rows}=={r['task_id']:r['package_sha256'] for r in identities},
                'final_sealed_native_roster_changed')
            world=json.loads(private(factory.PRIVATE/'partition_cases.json'))
            matches=[(family,case) for family,cases in world['cases'].items() for case in cases if case['id']==identity['task_id']]
            require(len(matches)==1,'final_hidden_case_missing_or_duplicate')
            family,case=matches[0]
            require(family in self.ROUTES and case.get('family')==family,'final_task_family_unbound')
            all_cases=[(name,item) for name,items in world['cases'].items() for item in items]
            require(len(all_cases)==100 and all(sum(name==family for name,_ in all_cases)==25 for family in self.ROUTES)
                and len({item['id'] for _,item in all_cases})==100
                and {item['id'] for _,item in all_cases}=={item['task_id'] for item in identities},'final_original_four_family_roster_required')
            other_ids={item['task_id'] for split,items in manifest.items() if split!='official' and type(items) is list for item in items}
            require(not other_ids&{item['task_id'] for item in identities},'final_split_identity_overlap')
            package_factory=importlib.import_module('partition_factory')
            require(Path(package_factory.__file__).resolve()==ROOT/'enterprise_fallback/odoo18/partition_factory.py','final_package_factory_unbound')
            asset=package_factory.source_asset(case,world)
            require(digest(json.dumps(case,sort_keys=True).encode()+b'\n'+asset)==identity['package_sha256'],
                'final_original_case_package_changed')
            self._cases={identity['task_id']:(family,case)};self._package_by_id={identity['task_id']:identity['package_sha256']}
            self.proof_context={'family':family,'target':json.loads(private(factory.PRIVATE/{'purchase':'development_gold.json',
                'inventory':'replenishment_gold.json','sales':'sales_gold.json','crm':'crm_gold.json'}[family]))[identity['task_id']],
                'baseline':json.loads(private(factory.PRIVATE/'baseline_snapshot.json')),
                'frozen_files':json.loads(private(factory.PRIVATE/'baseline-filestore-manifest.json'))}
            self.proof_root=Path(output);self.proofs=[]
            self._scored_snapshot_once=None
            parent=self
            def score(case_id):
                require(case_id==identity['task_id'],'final_scoring_wrong_task')
                observed=verify.snapshot();config=factory.local_config()
                physical=reset.filestore_manifest(config['ODOO_PROJECT']+'_filestore')
                paths=verify.attachment_store_paths(parent.proof_context['baseline'])
                verdict=_evaluate(family,case_id,parent.proof_context['target'],parent.proof_context['baseline'],observed,
                    physical,parent.proof_context['frozen_files'],paths,verify)
                proof={'schema':'odoo-final-live-saved-proof-v1','observed':observed,'physical_files':physical,
                    'attachment_paths':paths,'verdict':verdict,'context':parent.proof_context}
                reference=write(parent.proof_root,f'live-proof-{len(parent.proofs):02d}.private.json',proof)
                parent.proofs.append(reference);return verdict
            original_score=score
            def score_with_bound_readback(case_id):
                verdict=original_score(case_id)
                # One actual evaluator SELECT readback is both scored and
                # saved. The next independent reset snapshot is always fresh.
                proof=json.loads(private(parent.proof_root/parent.proofs[-1]['path']))
                parent._scored_snapshot_once=proof['observed']
                return verdict
            def snapshot():
                if parent._scored_snapshot_once is not None:
                    value=parent._scored_snapshot_once;parent._scored_snapshot_once=None
                    return value
                return verify.snapshot()
            self.verifier_proxy=SimpleNamespace(score=score_with_bound_readback,snapshot=snapshot)
    return Environment(worker)


class OdooNativeSurfaceFinalWorker:
    def __init__(self,*,gate,native_binding_path,native_binding_file_sha256,source_binding_path,source_binding_file_sha256,
        worker_dir,final_output_root,local_cost_authority_path,local_cost_authority_sha256,enable_live=False,
        native_worker_module=None):
        require(type(gate) is final.FinalGate,'real_final_gate_required')
        self.gate=gate;self.worker_dir=Path(worker_dir).resolve();self.output=Path(final_output_root).resolve();self.enable_live=enable_live
        self.binding_path=Path(native_binding_path);self.binding_sha=native_binding_file_sha256
        self.source_path=Path(source_binding_path);self.source_sha=source_binding_file_sha256
        self.cost_path=Path(local_cost_authority_path);self.cost_sha=local_cost_authority_sha256
        binding_raw=private(self.binding_path)
        require(digest(binding_raw)==self.binding_sha,'final_native_binding_file_changed')
        self.worker_module=module_from_binding(json.loads(binding_raw),native_worker_module)
        self.workers=_worker_module(self.worker_module)
        self.binding=self.workers.validate_binding(self.workers.private_json(self.binding_path,self.binding_sha))
        require(digest(private(self.source_path))==self.source_sha and json.loads(private(self.source_path))==source_binding(self.worker_module),
            'final_supplemental_source_binding_changed')
        require(self.output.is_relative_to(gate.work_root.resolve()),'final_output_outside_owned_work')
        self.cell=next(row for row in gate.plan['cells'] if row['cell_id']==CELL)
        require(self.cell['matched_bindings']['source_snapshot']==digest(final.canonical(study_source_snapshot(self.worker_module))),
            'final_supplemental_source_not_frozen_before_campaigns')
        self.identities=[{'task_id':r['task_id'],'package_sha256':r['package_sha256']} for chunk in self.cell['base']['chunks'] for r in chunk['tasks']]
        require(len(self.identities)==100 and len({r['task_id'] for r in self.identities})==100,'final_sealed_100_metadata_required')
        slots=[self.cell['base'],*self.cell['researcher_plans'].values()]
        require(len(slots)==5 and all(all(slot['bindings'][k]==self.cell['matched_bindings'][k] for k in
            ('source_snapshot','runtime','action_contract','verifier')) for slot in slots),'final_five_slot_bindings_differ')
        self._identity={'schema':final.WORKER_SCHEMA,'cell_id':CELL,'source_snapshot_sha256':self.cell['matched_bindings']['source_snapshot'],
            'runtime_sha256':self.binding['binding_sha256'],'action_contract_sha256':self.cell['matched_bindings']['action_contract'],
            'verifier_sha256':self.binding['source_sha256s']['enterprise_fallback/odoo18/verify.py'],
            'adapter_source_sha256':self.binding['source_sha256s'][self.workers.ADAPTER_FILE],
            'action_profile':'scale-action-profile-v0.6.6','observation_kind':'screenshot','actor_capability':'current_frame_gui_actions_only',
            'evaluator_isolated':True,'cold_reset_supported':True,'saved_state_readback_supported':True}
        final._worker_identity(self,self.cell,gate.frozen.ratification)

    @property
    def identity(self):return dict(self._identity)

    def _command(self,command,output_dir):
        require(self.enable_live is True,'final_explicit_live_required')
        self.workers.validate_binding(self.workers.private_json(self.binding_path,self.binding_sha))
        require(digest(private(self.source_path))==self.source_sha and json.loads(private(self.source_path))==source_binding(self.worker_module),
            'final_supplemental_source_binding_changed')
        require(type(command) is dict and set(command)==FIELDS and command['schema']==final.COMMAND_SCHEMA and
            command['cell_id']==CELL and command['study_id']==self.gate.plan['study_id'] and
            command['matched_bindings']==self.cell['matched_bindings'],'final_command_binding_changed')
        owner=command['owner_slot'];require(owner in self.cell['execution_evidence_owner_by_slot'].values(),'final_owner_unknown')
        slot=self.cell['base'] if owner=='shared-base' else self.cell['researcher_plans'][owner]
        identity={'task_id':command['task_id'],'package_sha256':command['package_sha256']}
        require(identity in self.identities,'final_task_outside_sealed_roster');ordinal=self.identities.index(identity)
        retry=command['retry_index']
        require(type(retry) is int and retry in (0,1) and command['attempt_id']==f'final-{matrix.CELLS.index(CELL):02d}-{owner}-{ordinal:03d}-{retry}' and
            command['retry_rule_sha256']==(final.RETRY_RULE_SHA256 if retry else None) and
            command['checkpoint_sha256']==slot['bindings']['checkpoint'] and command['sampling']==slot['sampling'] and
            command['max_actions']==slot['execution']['max_actions_per_task']==90 and command['max_wall_seconds']==slot['execution']['max_wall_seconds_per_task']==720 and
            command['expected_initial_state_sha256']==self.gate.initial_state_by_task[CELL][command['task_id']] and
            command['action_profile']=='scale-action-profile-v0.6.6','final_checkpoint_or_policy_changed')
        sampler=command['sampler_path']
        require((owner=='shared-base' and sampler is None) or (owner!='shared-base' and type(sampler) is str and
            final.SAMPLER_PATH.fullmatch(sampler) is not None and digest(sampler.encode())==command['checkpoint_sha256']),
            'final_sampler_not_bound')
        reserved=self.gate.budget.owner_attempts(CELL+':'+owner).get(command['attempt_id'])
        require(type(reserved) is dict and reserved['status']=='dispatched' and reserved['category']==('shared_base_final' if owner=='shared-base' else 'selected_final') and
            reserved['request_sha256']==digest(final.canonical(command)) and Decimal(reserved['reserved_usd'])==Decimal(command['reserve_usd']),
            'final_dispatched_reservation_required')
        output_dir=Path(output_dir)
        require(output_dir.parent.resolve()==self.output and output_dir.name==command['attempt_id'] and
            output_dir.is_dir() and not output_dir.is_symlink() and output_dir.stat().st_mode&0o077==0,'final_owned_output_required')

    def run_once(self,command,output_dir):
        self._command(command,output_dir);output_dir=Path(output_dir)
        write(output_dir,'worker-intent.private.json',{'schema':'odoo-final-worker-intent-v1','command_sha256':digest(final.canonical(command)),
            'native_binding_sha256':self.binding['binding_sha256'],'supplemental_source_sha256':self.source_sha,
            'five_slots_same_guard_sampler_reset_scorer':True,'automatic_replay':False})
        try:return self._episode(command,output_dir)
        except BaseException as error:
            write(output_dir,'worker-failure.private.json',{'schema':'odoo-final-worker-failure-v1',
                'command_sha256':digest(final.canonical(command)),'error_type':type(error).__name__,
                'error_code':getattr(error,'code',None),'formal_outcome_created':False,
                'provider_or_driver_completion_not_inferred':True,'automatic_replay':False})
            raise

    def _episode(self,command,output):
        _,selection=self.workers._model_modules(self.binding)
        training,_=self.gate.frozen.student_training_configuration()
        config={**training,'seed':command['sampling']['seed'],'sample_max_tokens':command['sampling']['max_output_tokens']}
        require(type(command['sampling']['temperature']) is str and Decimal(command['sampling']['temperature'])==0
            and training['model']=='Qwen/Qwen3.8-27B','final_frozen_sampler_changed')
        authority=selection._cost_authority(self.cost_path,self.cost_sha)
        runtime_gate.pre_dispatch(repo_root=self.gate.frozen.repo_root,study_plan_sha256=self.gate.frozen.plan_sha256)
        require(bool(os.environ.get('TINKER_API_KEY')),'final_tinker_key_missing')
        started_at=int(time.time());started=time.monotonic();episode=output/'native-episode';episode.mkdir(mode=0o700)
        identity={'task_id':command['task_id'],'package_sha256':command['package_sha256']}
        environment=environment_factory(selection,self.worker_dir,self.identities,self.binding)
        environment._native_readiness_sink=lambda value:write(episode,'db-readiness.private.json',value)
        # Only now, after FinalGate/command/reservation/intent checks, can the
        # evaluator open hidden bodies. The sampler sees only GUI observations.
        environment.load_command_task(identity,episode)
        base=command['owner_slot']=='shared-base'
        sampler=selection.RealTinkerSelectionSampler(checkpoint_path='Qwen/Qwen3.8-27B' if base else command['sampler_path'],
            config=config,output_root=episode,attempt_id=command['attempt_id'],base_mode=base,
            expected_base_checkpoint_sha256=command['checkpoint_sha256'] if base else None)
        timing=[]
        class MeteredSampler:
            def __init__(self,delegate):self.delegate=delegate
            def sample(self,observation,**kwargs):
                index=len(timing)
                write(episode,f'final-sample-{index:03d}-intent.private.json',{'schema':'odoo-final-current-frame-sample-v1',
                    'task_id':observation.task_id,'package_sha256':observation.task_binding_sha256,'step':observation.step,
                    'frame_id_sha256':digest(observation.frame_id.encode()),'frame_sha256':observation.screenshot['sha256'],
                    'checkpoint_sha256':command['checkpoint_sha256'],'existing_parent_reservation':command['attempt_id'],
                    'no_automatic_replay':True})
                sample_started=time.monotonic()
                result=self.delegate.sample(observation,**kwargs)
                elapsed=time.monotonic()-sample_started;timing.append(elapsed)
                write(episode,f'final-sample-{index:03d}-result.private.json',{'schema':'odoo-final-sample-result-v1',
                    'result':result,'provider_latency_seconds':elapsed})
                require(type(result) is dict and result.get('status')=='completed' and result.get('new_dispatch') is True
                    and result.get('reused') is False and type(result.get('text')) is str,'final_provider_result_uncertain_no_replay')
                usage=result.get('usage')
                require(type(usage) is dict and all(type(usage.get(k)) is int for k in ('input_tokens','image_tokens','output_tokens'))
                    and 0<usage['input_tokens']<=selection.MAX_INPUT_TOKENS and 0<usage['image_tokens']<=usage['input_tokens']
                    and 0<=usage['output_tokens']<=config['sample_max_tokens'],'final_provider_usage_uncertain_no_replay')
                # The controller's existing whole-task paid reservation covers
                # every frame. This is its actual ID, not an invented paid call.
                return {**result,'rendered_usage':usage,'paid_attempt_id':command['attempt_id']}
        with sampler as active_sampler:
            with environment.batch() as active:
                row=active.run_case(identity,0,MeteredSampler(active_sampler),episode)
        selection._audit_task_artifacts(episode,identity,row)
        self.workers.audit_readiness_receipt(episode/'db-readiness.private.json',self.binding,self.worker_dir)
        environment.provider_latencies=timing
        return self._outcome(command,output,episode,row,environment,selection,training,authority,started_at,started)

    def _outcome(self,command,output,episode,row,environment,selection,training,authority,started_at,started):
        saved=json.loads(private(episode/'saved-state.private.json'));reset=json.loads(private(episode/'reset.private.json'))
        baseline=json.loads(private(episode/'baseline-semantic.private.json'));restored=json.loads(private(episode/'restored-semantic.private.json'))
        require(reset['post_database_filestore_exact'] is True and baseline==restored and
            reset['baseline_semantic_sha256']==reset['restored_semantic_sha256'] and
            digest(selection._canonical(baseline['business_snapshot']))==command['expected_initial_state_sha256'],
            'final_exact_initial_and_restored_state_required')
        require(type(saved.get('business_snapshot')) is dict and len(environment.proofs)>=2,'final_saved_readback_proof_required')
        proof=json.loads(private(episode/environment.proofs[-1]['path']))
        require(proof['observed']==saved['business_snapshot'] and proof['context']==environment.proof_context,
            'final_scored_snapshot_not_saved_readback')
        verify=_modules(self.worker_dir,self.binding)[3]
        verdict=_evaluate(proof['context']['family'],command['task_id'],proof['context']['target'],proof['context']['baseline'],
            saved['business_snapshot'],proof['physical_files'],proof['context']['frozen_files'],proof['attachment_paths'],verify)
        require(verdict==proof['verdict'],'final_saved_verdict_rederivation_changed')
        actions=json.loads(private(episode/'actions.private.json'));frames=json.loads(private(episode/'frames.private.json'))
        usage=json.loads(private(episode/'usage.private.json'));samples=usage['samples']
        require(len(frames)==len(samples) and samples and all(s['status']=='completed' for s in samples),'final_native_sample_coverage_missing')
        for item in actions:
            observed=private(episode/frames[item['step']]['path'])
            self.workers.audit_native_contract(item['contract_receipt'],item['native_action'],observed,item['step'],
                {'task_id':command['task_id'],'package_sha256':command['package_sha256']},episode,
                observation_control_refs=item['native_observation_control_refs'])
        require(environment.runtime_receipt['services_restored_to_initial_state'] is True and
            environment.runtime_receipt['final_database_snapshot_equal'] is True and environment.runtime_receipt['final_physical_filestore_equal'] is True,
            'final_batch_reset_and_cleanup_missing')
        subtype={'task_action_budget':'actor_action_budget','task_wall_budget':'actor_wall_budget'}.get(row['termination'],'none')
        native_score=int(verdict['reward']==1.0 and verdict['checks_passed'] is True and verdict['difference_codes']==[])
        require(native_score==row['score'],'final_native_score_changed')
        score=native_score if subtype=='none' else 0
        inputs=sum(s['usage']['input_tokens'] for s in samples);outputs=sum(s['usage']['output_tokens'] for s in samples)
        image_tokens=sum(s['usage'].get('image_tokens',0) for s in samples)
        cost=(Decimal(inputs)*Decimal(training['prefill_usd_per_million_tokens'])+Decimal(outputs)*Decimal(training['sample_usd_per_million_tokens']))/Decimal(1_000_000)
        cost*=Decimal(training['billing_multiplier_upper'])
        cost+=Decimal(str(environment.runtime_receipt['elapsed_seconds']))/Decimal(3600)*Decimal(authority['hourly_usd_upper'])
        require(cost<=Decimal(command['reserve_usd']),'final_nominal_cost_over_reservation')
        cost=str(cost.quantize(Decimal('.000000001')))
        refs={}
        refs['usage']=write(output,'usage.private.json',{'schema':final.USAGE_SCHEMA,'attempt_id':command['attempt_id'],
            'cost_basis':'published_rate_nominal','cost_usd':cost,'input_tokens':inputs,'image_tokens':image_tokens,'output_tokens':outputs,
            'provider_billed_tokens':None,'provider_invoice_sha256':None})
        refs['reset']=write(output,'cold-reset.private.json',{'schema':final.RESET_SCHEMA,'task_id':command['task_id'],
            'package_sha256':command['package_sha256'],'attempt_id':command['attempt_id'],'fresh_environment':True,'restored_after_attempt':True,
            'initial_state_sha256':command['expected_initial_state_sha256'],'restored_state_sha256':command['expected_initial_state_sha256']})
        refs['saved_state']=final.reference(output,episode/'saved-state.private.json')
        refs['verifier']=write(output,'independent-verifier.private.json',{'schema':final.VERIFIER_SCHEMA,'task_id':command['task_id'],
            'package_sha256':command['package_sha256'],'attempt_id':command['attempt_id'],'saved_state_sha256':refs['saved_state']['sha256'],
            'score':score,'no_regression_checked':True,'no_regression_passed':bool(verdict['checks_passed']),
            'independent_of_actor':True,'gold_withheld_from_actor':True})
        count=sum(a['native_dispatch_status']=='applied' for a in actions)
        refs['observation_trace']=write(output,'observations.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':command['attempt_id'],
            'kind':'observations','action_profile':'scale-action-profile-v0.6.6','count':len(samples),'screenshot_only':True})
        refs['action_trace']=write(output,'actions.private.json',{'schema':final.TRACE_SCHEMA,'attempt_id':command['attempt_id'],
            'kind':'actions','action_profile':'scale-action-profile-v0.6.6','count':count,'current_frame_validated':True})
        wall=int((time.monotonic()-started)*1000)
        latency=sum(int(seconds*1000) for seconds in environment.provider_latencies)
        require(wall<=command['max_wall_seconds']*1000 and latency<=wall,'final_complete_wall_over_budget')
        return {'schema':final.OUTCOME_SCHEMA,'status':'scored','score':score,'failure_type':None,'started_at':started_at,
            'finished_at':int(time.time()),'cost_basis':'published_rate_nominal','cost_usd':cost,**refs,'action_count':count,
            'turn_count':len(samples),'wall_time_ms':wall,'provider_latency_ms':latency,'timeout_subtype':subtype,
            'action_profile':'scale-action-profile-v0.6.6'}


def final_worker_factory(**kwargs):return OdooNativeSurfaceFinalWorker(**kwargs)
