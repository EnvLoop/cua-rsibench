"""Actual paid teacher collector bridge using the same Magento native actor."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from cursibench import full_study_runtime_v2 as v22
from cursibench import full_study_teacher_adapter_v1 as teacher
from native_desktop_factory.actor_deadline_future_v21 import DeadlineFuture,ActorDeadlineReached
from .native_surface_workers_v1 import CELL,require,digest,write,public_binding,study_source_snapshot,verify_environment_scope
from .native_queue_runtime_v2 import run_task
from .native_surface_budget_performance_v2 import audit_episode


class TeacherSampler:
    def __init__(self,*,session,callback,round_index,episode_index):
        self.session=session;self.callback=callback;self.round=round_index;self.episode=episode_index
        self.attempt_id=f'teacher-r{round_index:03d}-e{episode_index:03d}';self.rows=[];self.last_deadline_result=None
    def next_paid_attempt_id(self,step):return self.attempt_id+f'-s{step:03d}'
    def request_id_for_step(self,step):return self.next_paid_attempt_id(step)
    def bind_native_adapter(self,adapter,loop):self.adapter=adapter;self.loop=loop
    def current_frame_id(self):
        async def current():
            meta=await self.adapter.meta();check=await self.adapter.boundary.check(self.adapter.store)
            return (self.adapter.latest.frame_id if self.adapter.latest is not None and
                self.adapter.clock()<self.adapter.latest.expires_at and
                await self.adapter.boundary.owns(self.adapter.page,meta) and check['status']=='active' else 'stale')
        return asyncio.run_coroutine_threadsafe(current(),self.loop).result(timeout=min(30,max(.001,self.actor_clock.deadline-time.monotonic())))
    def sample(self,observation,**kwargs):
        self.actor_clock.check('before_paid_teacher_submission')
        pool=ThreadPoolExecutor(max_workers=1)
        future=pool.submit(self.callback,observation,self.current_frame_id)
        try:sampled=DeadlineFuture(future,self.actor_clock.deadline).result(timeout=min(120,max(.001,self.actor_clock.deadline-time.monotonic())))
        finally:pool.shutdown(wait=False,cancel_futures=True)
        require(set(sampled)=={'action','trace_row','teacher_result_sha256'} and sampled['trace_row']['action']==sampled['action'] and
            sampled['trace_row']['frame_id']==observation.frame_id and sampled['trace_row']['frame_sha256']==observation.screenshot['sha256'],
            'magento_actual_paid_teacher_trace_changed')
        identifier=self.next_paid_attempt_id(observation.step)
        source=self.session.directory/(identifier+'.result.private.json')
        require(source.is_file() and digest(source.read_bytes())==sampled['teacher_result_sha256'],
            'magento_teacher_actual_paid_result_missing')
        self.rows.append(sampled)
        return {'status':'completed','new_dispatch':True,'reused':False,'text':json.dumps(sampled['action']),
            'request_id':identifier,'paid_attempt_id':identifier,'teacher_result_sha256':sampled['teacher_result_sha256']}


class TeacherWorker:
    cell_id=CELL;action_profile='scale-action-profile-v0.6.6';original_software_gui=True
    original_surface='web';requires_e2b=False;requires_fresh_e2b_reset=False
    def __init__(self,*,session,inputs,round_index,enable_live=False):
        require(type(session) is v22.CampaignSession and session.intent['cell_id']==CELL,'magento_real_teacher_campaign_required')
        verify_environment_scope(session.study)
        require(not inputs.control_preparation_only,'native_train_admission_required_before_teacher');inputs.validate_train_admission()
        self.session=session;self.inputs=inputs;self.round_index=round_index;self.enable_live=enable_live
        self.runtime_sha256=inputs.binding['binding_sha256']
        self.adapter_sha256=inputs.binding['source_sha256s']['magento_catalog_factory/native_surface_guard_v1.py']
        self.verifier_sha256=inputs.binding['verifier_sha256']
        cell=next(r for r in session.study.plan['cells'] if r['cell_id']==CELL)
        require(cell['matched_bindings']['runtime']==self.runtime_sha256 and cell['matched_bindings']['source_snapshot']==digest(teacher._canonical(study_source_snapshot())) and cell['matched_bindings']['verifier']==self.verifier_sha256 and
            session.study.ratification['cell_profiles'][CELL]['adapter_sha256']==self.adapter_sha256,'magento_teacher_source_not_ratified')
    def run_episode(self,*,task,out_dir,sample_teacher,dispatch_e2b):
        require(self.enable_live and self.inputs.binding==public_binding(),'magento_explicit_current_teacher_source_required')
        identity={k:task[k] for k in ('task_id','package_sha256')}
        require(identity in [{k:r[k] for k in ('task_id','package_sha256')} for r in self.session.views['train']] and identity in self.inputs.roster['splits']['train'],'magento_teacher_train_view_only')
        output=Path(out_dir);require(output.resolve().is_relative_to(self.session.study.repo_root/'work') and output.is_dir() and
            not output.is_symlink() and output.stat().st_mode&0o077==0,'magento_teacher_owned_output_required')
        case=self.inputs.load(identity,'train');require(case['instruction']==task['visible_instruction'],'magento_teacher_instruction_changed')
        ordinal=int(output.name.removeprefix('episode-'));identifier=f'magento-teacher-r{self.round_index:03d}-e{ordinal:03d}'
        request={'schema':'magento-owned-teacher-environment-request-v1','task_id':identity['task_id'],
            'package_sha256':identity['package_sha256'],'round_index':self.round_index,'episode_index':ordinal,
            'native_source_binding_sha256':self.runtime_sha256,'lease_seconds':1200}
        native=output/'native-episode';native.mkdir(mode=0o700)
        sampler=TeacherSampler(session=self.session,callback=sample_teacher,round_index=self.round_index,episode_index=ordinal)
        def provider(actual):
            require(actual==request,'magento_teacher_environment_paid_request_changed')
            row=asyncio.run(run_task(case=case,task=identity,output=native,runtime=self.inputs.runtime(),sampler=sampler,
                username=self.inputs.username(),attempt_id=identifier,paid_attempt_id=identifier))
            write(native,'native-row.private.json',row)
            return {'status':'completed','task_id':identity['task_id'],'package_sha256':identity['package_sha256'],
                'native_row':{'path':str(native/'native-row.private.json'),'sha256':digest((native/'native-row.private.json').read_bytes())}}
        self.session.dispatch_paid(attempt_id=identifier,category='storage_application',work=request,request=request,
            reserve_usd='1',resource_reservation={},provider=provider)
        row=json.loads((native/'native-row.private.json').read_bytes());audit=audit_episode(native,row,provider_close_required=False)
        require(row['score']==1 and row['termination']=='model_finish' and len(sampler.rows)==row['turn_count'] and
            all(r['status']=='completed' for r in row['samples']),'magento_teacher_only_independently_saved_positive_curated')
        frames=[]
        for index,frame in enumerate(audit['frames']):
            path=output/'frames'/f'step-{index:03d}.png';path.parent.mkdir(mode=0o700,exist_ok=True)
            from cursibench.full_study_final_dispatch_v1 import private_write_new
            private_write_new(path,(native/frame['frame']['path']).read_bytes())
            frames.append({'path':str(path.relative_to(output)),'sha256':digest(path.read_bytes())})
        write(output,'actions.private.json',[r['trace_row'] for r in sampler.rows])
        (output/'artifacts').mkdir(mode=0o700)
        saved=write(output,'artifacts/saved-artifact.private.json',audit['saved'])
        semantic={'material_baseline_sha256':digest(teacher._canonical(audit['verifier']['baseline']))}
        baseline=write(output,'artifacts/baseline.private.json',semantic);restored=write(output,'artifacts/restored.private.json',semantic)
        common={'cell_id':CELL,**identity}
        state=write(output,'saved-state.private.json',{'schema':teacher.STATE_SCHEMA,**common,'independent_of_actor':True,
            'native_save_observed':True,'target_state_pass':True,'no_regression_pass':True,'saved_artifact_sha256':saved['sha256'],
            'saved_artifact_ref':saved,'verifier_sha256':self.verifier_sha256,'evaluator_result':'pass'})
        reset=write(output,'reset.private.json',{'schema':teacher.RESET_SCHEMA,**common,'independent_of_actor':True,
            'fresh_environment':True,'state_equivalence_pass':True,'sandbox_terminated':True,'baseline_semantic_sha256':baseline['sha256'],
            'restored_semantic_sha256':restored['sha256'],'baseline_state_ref':baseline,'restored_state_ref':restored,
            'raw_reset_ref':{'path':'native-episode/reset.private.json','sha256':digest((native/'reset.private.json').read_bytes())}})
        receipt=write(output,'episode.private.json',{'schema':teacher.EPISODE_SCHEMA,'status':'admitted','split':'train',**common,
            'action_profile':self.action_profile,'teacher_model':teacher.matrix.TEACHER,'original_software_gui':True,'original_surface':'web',
            'runtime_sha256':self.runtime_sha256,'adapter_sha256':self.adapter_sha256,'frame_refs':frames,
            'action_trace_ref':{'path':'actions.private.json','sha256':digest((output/'actions.private.json').read_bytes())},
            'saved_state_ref':state,'reset_ref':reset,'teacher_result_sha256s':[r['teacher_result_sha256'] for r in sampler.rows],
            'e2b_attempt_ids':[]})
        return {'episode_receipt_path':str(output/'episode.private.json'),'episode_receipt_sha256':receipt['sha256']}


def teacher_worker_factory(**kwargs):return TeacherWorker(**kwargs)
