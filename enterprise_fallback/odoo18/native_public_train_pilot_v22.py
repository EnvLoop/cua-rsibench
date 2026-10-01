"""One genuinely paid public TRAIN development pilot, with no formal authority."""
from __future__ import annotations
from hashlib import sha256
from types import FunctionType
import inspect,json,os,re,sys,time
from pathlib import Path
from . import native_surface_final_worker_v22 as final_source
from . import native_surface_final_worker_v1 as legacy
from . import native_surface_workers_v13 as workers
from .odoo_actor_model_modules_v1 import run_owned_task
from .odoo_no_retry_sampler_v22 import sampler_class

ROOT=legacy.ROOT
require,private,digest,write=legacy.require,legacy.private,legacy.digest,legacy.write
FILES=('enterprise_fallback/odoo18/native_public_train_pilot_v22.py','tools/odoo_public_train_model_pilot_v22.py',
 'enterprise_fallback/odoo18/odoo_no_retry_sampler_v22.py','enterprise_fallback/odoo18/native_surface_final_worker_v1.py',
 'enterprise_fallback/odoo18/native_surface_final_worker_v22.py')
FIELDS={'schema','attempt_id','worker_dir','output_root','native_binding','train_control','task','training_config','source_binding_sha256'}


def source_binding():
    native=workers.public_binding()
    value={'schema':'odoo-public-train-pilot-source-v22','native_binding_sha256':native['binding_sha256'],
        'source_sha256s':{**native['source_sha256s'],**{n:digest((ROOT/n).read_bytes()) for n in (*FILES,*final_source.FILES)}},
        'max_actions':90,'actor_seconds':720,'lifecycle_seconds':1200,'formal_admission_permitted':False,
        'all_consumed_requests_no_replay':True,'model':'Qwen/Qwen3.8-27B'}
    return {**value,'binding_sha256':digest(legacy.final.canonical(value))}


def read_ref(reference):
    require(type(reference) is dict and set(reference)=={'path','sha256'},'pilot_private_reference_required')
    raw=private(reference['path']);require(digest(raw)==reference['sha256'],'pilot_private_reference_changed')
    return json.loads(raw)


def modules(worker,binding):
    code=ROOT/'enterprise_fallback/odoo18';os.environ['ENVLOOP_ODOO_WORKER_DIR']=str(worker)
    if str(code) not in sys.path:sys.path.insert(0,str(code))
    result=[]
    for name in ('factory','gui_controls','reset','verify','worker_lease'):
        module=sys.modules.get(name)
        require(module is None or Path(module.__file__).resolve()==code/(name+'.py'),'pilot_module_identity_conflict')
        import importlib
        module=importlib.import_module(name);result.append(module)
    factory,gui,reset,verify,lease=result
    require(worker.name=='train' and factory.HERE==worker and factory.PRIVATE==worker/'private' and
        reset.HERE==worker and verify.PRIVATE==factory.PRIVATE and gui.PRIVATE==factory.PRIVATE and lease.PRIVATE==factory.PRIVATE and
        factory.local_config().get('ODOO_PARTITION')=='train' and not (worker/'compose.yaml').is_symlink() and digest((worker/'compose.yaml').read_bytes())==binding['source_sha256s']['enterprise_fallback/odoo18/compose.yaml'],
        'pilot_original_train_worker_not_bound')
    private(worker/'.env');require((worker/'private').stat().st_mode&0o077==0,'pilot_private_train_directory_required')
    return result


def train_environment(selection,worker,identities,binding):
    # An exact checked partition bridge; actor/scorer/reset implementations stay V13.
    source=inspect.getsource(legacy.environment_factory)
    replacements=(("rows=manifest.get('official')","rows=manifest.get('train')"),
        ('len(rows)==100','len(rows)==20'),('len(all_cases)==100','len(all_cases)==20'),
        ('==25 for family','==5 for family'),('})==100','})==20'),("split!='official'","split!='train'"))
    for before,after in replacements:
        require(source.count(before)==1,'pilot_checked_partition_bridge_source_changed');source=source.replace(before,after)
    namespace=dict(legacy.environment_factory.__globals__);namespace['_modules']=modules
    exec(compile(source,'checked-odoo-public-train-partition-bridge-v22','exec'),namespace)
    return namespace['environment_factory'](selection,worker,identities,binding)


class PaidPilotSampler(final_source.MeteredSampler):
    def __enter__(self):
        self.setup_intent=write(self.episode,'paid-setup-intent.private.json',{'schema':'odoo-public-train-paid-setup-intent-v22',
            'paid_attempt_id':self.command['attempt_id'],'model':'Qwen/Qwen3.8-27B','sampling_kind':'base',
            'http_max_retries':0,'sampling_retry_enabled':False,'same_request_replay_authorized':False,'actual_cost_usd':None})
        try:returned=super().__enter__()
        except Exception as error:
            write(self.episode,'paid-setup-uncertain.private.json',{'error_type':type(error).__name__,'actual_cost_usd':None,'request_replayed':False});raise
        try:
            self.setup_result=write(self.episode,'paid-setup-result.private.json',{'schema':'odoo-public-train-paid-setup-result-v22',
                'status':'ready','actual_backend_identity':self.delegate.backend.identity,'paid_attempt_id':self.command['attempt_id'],
                'actual_cost_usd':None,'provider_invoice_sha256':None})
        except Exception:
            # A setup evidence failure cannot leave a successfully opened provider owned.
            self.delegate.__exit__(*sys.exc_info())
            raise
        return returned


class PublicTrainPilot:
    def __init__(self,request,review,*,enable_live=False):
        require(type(request) is dict and set(request)==FIELDS and request['schema']=='odoo-public-train-model-pilot-request-v22','pilot_request_exact_fields_required')
        require(re.fullmatch(r'public-train-[A-Za-z0-9_-]{1,80}',str(request['attempt_id'])) is not None,'pilot_unique_attempt_id_required')
        self.source=source_binding()
        require(request['source_binding_sha256']==self.source['binding_sha256'],'pilot_current_source_binding_required')
        require(review=={'schema':'odoo-public-train-model-pilot-root-review-v22','request_sha256':digest(legacy.final.canonical(request)),
            'source_binding_sha256':self.source['binding_sha256'],'one_public_train_paid_pilot_authorized':True,
            'formal_registration_authorized':False,'automatic_retry_authorized':False},'pilot_exact_root_review_required')
        self.binding=workers.validate_binding(read_ref(request['native_binding']))
        workers.validate_train_control(read_ref(request['train_control']),self.binding)
        require(type(request['task']) is dict and set(request['task'])=={'task_id','package_sha256'} and re.fullmatch(r'[0-9a-f]{64}',str(request['task']['package_sha256'])),'pilot_public_train_identity_required')
        config=request['training_config']
        require(type(config) is dict and set(config)=={'model','seed','sample_max_tokens'} and config['model']=='Qwen/Qwen3.8-27B' and
            type(config['seed']) is int and 0<=config['seed']<2**31 and type(config['sample_max_tokens']) is int and 0<config['sample_max_tokens']<=4096,'pilot_frozen_qwen_sampling_required')
        self.worker=Path(request['worker_dir']).resolve();self.output=Path(request['output_root']).resolve()
        require(self.worker.name=='train' and self.output.is_relative_to(ROOT/'work') and not self.output.is_symlink(),'pilot_owned_public_train_scope_required')
        self.request=request;self.enable_live=enable_live

    def run_once(self):
        require(self.enable_live is True,'pilot_explicit_live_required')
        require(self.source==source_binding(),'pilot_source_changed_before_dispatch')
        require(not self.output.exists() and not self.output.is_symlink(),'pilot_consumed_output_no_replay')
        self.output.mkdir(parents=True,mode=0o700)
        # Durable paid intent consumes this unique attempt before any SDK/native setup.
        write(self.output,'paid-parent-intent.private.json',{'schema':'odoo-public-train-paid-intent-v22','attempt_id':self.request['attempt_id'],
            'request_sha256':digest(legacy.final.canonical(self.request)),'source_binding_sha256':self.source['binding_sha256'],
            'actual_usd':None,'invoice_sha256':None,'same_request_replay_authorized':False,'formal_credit':0})
        require(bool(os.environ.get('TINKER_API_KEY')),'pilot_tinker_key_missing')
        _,selection=workers._model_modules(self.binding)
        factory,_,_,_,_=modules(self.worker,self.binding)
        manifest=json.loads(private(factory.PRIVATE/'task_set_manifest.json'));identities=manifest.get('train')
        require(type(identities) is list and len(identities)==20 and self.request['task'] in identities,'pilot_task_not_in_public_train_partition')
        environment=train_environment(selection,self.worker,identities,self.binding)
        environment._native_readiness_sink=lambda value:write(self.output,'db-readiness.private.json',value)
        environment.load_command_task(self.request['task'],self.output)
        delegate=sampler_class(selection)(checkpoint_path='Qwen/Qwen3.8-27B',config=self.request['training_config'],output_root=self.output,
            attempt_id=self.request['attempt_id'],base_mode=True,expected_base_checkpoint_sha256=digest(b'Qwen/Qwen3.8-27B'))
        sampler=PaidPilotSampler(delegate,self.output,{'attempt_id':self.request['attempt_id']});sampler.parent_paid_attempt_id=self.request['attempt_id']
        try:
            row=run_owned_task(environment=environment,task=self.request['task'],index=0,sampler=sampler,task_dir=self.output,attempt_id=self.request['attempt_id'])
            selection._audit_task_artifacts(self.output,self.request['task'],row)
            workers.audit_readiness_receipt(self.output/'db-readiness.private.json',self.binding,self.worker)
            write(self.output,'pilot-result.private.json',{'schema':'odoo-public-train-model-pilot-result-v22','status':'independently_saved_scored_and_reset',
                'task':self.request['task'],'native_binding_sha256':self.binding['binding_sha256'],'source_binding_sha256':self.source['binding_sha256'],
                'native_row':row,'actual_usage':json.loads(private(self.output/'usage.private.json')),
                'paid_setup_intent':sampler.setup_intent,'paid_setup_result':sampler.setup_result,'paid_sample_calls':sampler.calls,
                'actual_cost_usd':None,'provider_invoice_sha256':None,'formal_credit':0,'formal_registration_performed':False})
            return row
        except Exception as error:
            write(self.output,'pilot-failure.private.json',{'schema':'odoo-public-train-model-pilot-failure-v22','error_type':type(error).__name__,
                'error_sha256':digest(str(error).encode()),'runtime_cleanup':environment.runtime_receipt,'request_replayed':False,
                'actual_cost_usd':None,'formal_credit':0});raise
