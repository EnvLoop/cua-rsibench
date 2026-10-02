"""Metadata-first current Office execution using actual witnessed v22 authorities."""
import argparse,importlib,json,sys
from pathlib import Path
from tools.office_current_authority_v4 import Authority,current_sources
from tools.office_current_execution_v4 import TaskWorker
from tools.office_current_protocol_v4 import epoch_context,source_manifest
from tools.office_current_workers_v4 import run_selection,admit_shared_base,TrustedFinalWorker
from tools import office_owned_folder_runtime_v2 as office
from cursibench import full_study_runtime_v2 as policy


def load(config):
 # Study/600 qualification precedes native profile, package body and process.
 args={k:Path(v) if k in ('repo_root','parent_manifest','parent_prepared','ratification','parent_witness','policy_dir') else v for k,v in config['policy_loading'].items()}
 study=policy.load_policy_study(**args);office.require(config['cell_id'] in office.CELLS,'Original Office cell required');return study


def worker_options(study,config):
 options={}
 for key in ('metadata_index','binding_path','profile_path','qualification_path'):
  ref=config['worker'][key];path=Path(ref['path']);office.require(path.resolve().is_relative_to(study.repo_root/'work') and office.sha(office.private(path))==ref['sha256'],'Private source-qualified Office packet changed');options[key]=path
 options['qualification_sha256']=config['worker']['qualification_path']['sha256'];return options


def final_controller(study,config):
 from cursibench.full_study_final_performance_v2 import FinalController
 args={k:Path(v) if k.endswith('_path') or k=='prepared_matrix_dir' else v for k,v in config['final_gate'].items() if k!='policy_final_witness_ref'}
 ref=config['final_gate']['policy_final_witness_ref'];raw=office.private(Path(ref['path']));office.require(office.sha(raw)==ref['sha256'],'Exact immutable final witness changed')
 gate=policy.FinalGate(study,policy_final_witness_bytes=raw,**args)
 factory=config['formal_worker_factory'];name=factory['module'].replace('.','/')+'.py'
 office.require(source_manifest(study.repo_root)['source_sha256s'].get(name)==factory['source_sha256'],'All-six concrete worker factory must join fresh frozen source closure')
 module=importlib.import_module(factory['module']);office.require(Path(module.__file__).resolve()==study.repo_root/name,'All-six factory import identity changed')
 workers=getattr(module,factory['function'])(study=study,gate=gate,configuration=config)
 for cell in office.CELLS:office.require(type(workers[cell]) is TrustedFinalWorker,'Actual current PPT/Excel trusted final workers required')
 return FinalController(gate,workers=workers,sampler_bindings_path=Path(config['sampler_bindings_path']),output_dir=Path(config['output_root']))


def execute(config,mode,enable_native=False):
 office.require(config['schema']=='office-current-execution-configuration-v4','Actual current execution configuration required')
 with epoch_context():study=load(config)
 with epoch_context(study):
  if mode=='run-final':
   controller=final_controller(study,config);office.require(enable_native,'Current formal native execution disabled')
   return controller.run_task(config['cell_id'],config['owner_slot'],config['task_id']) if config.get('task_id') else controller.run_all()
  options=worker_options(study,config)
  if mode=='check':
   from tools.office_current_authority_v4 import verify_qualification
   verify_qualification(study,config['cell_id'],options['qualification_path'],options['qualification_sha256'])
   return {'status':'actual_study_and_source_qualification_checked_before_session_provider','model_calls':0,'native_calls':0}
  if config['owner_slot']=='shared-base':session=policy.SharedBaseSession(study,config['cell_id']);started=None
  else:
   session=study.open_campaign(Path(config['session_directory']),cell_id=config['cell_id'],researcher_id=config['owner_slot'])
   started=json.loads(office.private(Path(config['selection_start_path']))) if mode!='run-teacher' and config.get('selection_start_path') else None
  if mode=='run-teacher':
   from tools.office_current_teacher_v4 import TeacherWorker,collect_train_batch
   worker=TeacherWorker(session=session,worker_options=options,quote=config['reservation_quote_usd']);office.require(enable_native,'Current teacher native execution disabled')
   result=collect_train_batch(session,config['round_index'],Path(config['train_context_path']),Path(config['output_root']),worker)
   return {'status':'actual_teacher_batch_rendered','episode_count':len(result.episode_receipt_sha256s),'dataset_manifest_path':str(result.dataset_manifest_path),'cost_usd':None}
  authority=Authority(authority=study,cell_id=config['cell_id'],owner_slot=config['owner_slot'],session=session,started=started)
  worker=TaskWorker(authority=authority,output_root=Path(config['output_root']),**options)
  office.require(enable_native,'Current native execution disabled');result=run_selection(worker,quote=config['reservation_quote_usd'],register=authority.owner!='shared-base')
  if authority.owner=='shared-base':admitted=admit_shared_base(worker,result)
  else:admitted=result['registration']
  return {'status':'actual_twenty_task_selection_registered','task_count':20,'wins':sum(r['score'] for r in result['result']['tasks']),'actual_cost_usd':None,'invoice_complete':False,'registration':admitted}


def main():
 if len(sys.argv)>1 and sys.argv[1]=='policy':
  sys.argv.pop(1)
  with epoch_context():policy.main()
  return
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('sources','check','run-selection','run-shared','run-teacher','run-final'));p.add_argument('--repo-root',type=Path);p.add_argument('--config',type=Path);p.add_argument('--enable-native',action='store_true');args=p.parse_args()
 if args.mode=='sources':
  office.require(args.repo_root is not None,'Actual code root required');print(json.dumps({'source_sha256s':current_sources(args.repo_root),'native_qualified':False,'model_calls':0}));return
 office.require(args.config is not None,'Private immutable execution configuration required');result=execute(json.loads(office.private(args.config)),args.mode,args.enable_native);print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
