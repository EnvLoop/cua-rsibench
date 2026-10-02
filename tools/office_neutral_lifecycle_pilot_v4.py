"""One reviewed TRAIN neutral native lifecycle; no model/provider sampler.

Preparation and check are read-only with respect to native software. Run is
one-use and waits for Root's explicit CUA pump; missing/uncertain operations
are retained and never replayed. This is not formal qualification.
"""
from __future__ import annotations
import argparse,json,time
from pathlib import Path
from tools import office_owned_folder_runtime_v2 as runtime
from tools.office_owned_folder_spool_v2 import NativeOperationSpool
from cursibench.scale_action_output_v066 import normalize_model_action

V4_FILES=('tools/office_owned_folder_cua_pump_v4.mjs','tools/office_owned_folder_cua_host_v3.mjs',
 'tools/office_owned_folder_native_extractor_v3.mjs','tools/office_owned_folder_native_profile_v3.mjs',
 'tools/office_owned_folder_ui_lifecycle_v4.mjs','tools/office_signed_in_principal_v3.mjs','tools/office_document_download_v4.mjs')


def source_hashes(repo):
 root=Path(repo).resolve();return {name:runtime.sha((root/name).read_bytes()) for name in (*runtime.SOURCE_FILES,*V4_FILES,'tools/office_neutral_lifecycle_pilot_v4.py')}


def reference(path):return {'path':str(Path(path).resolve()),'sha256':runtime.sha(runtime.private(path))}


def read_ref(ref):
 runtime.require(type(ref) is dict and set(ref)=={'path','sha256'},'Exact private reference required')
 path=Path(ref['path']);raw=runtime.private(path);runtime.require(runtime.sha(raw)==ref['sha256'],'Private pilot reference changed');return path,raw


def prepare(*,repo_root,package_descriptor,package_root,binding_path,profile_path,output,config_path):
 repo=Path(repo_root).resolve();output=Path(output).absolute();config_path=Path(config_path).absolute()
 runtime.require(not output.exists() and not output.is_symlink() and output.parent.resolve().is_relative_to(repo/'work'),'Fresh owned pilot output required')
 package=runtime.Package(package_descriptor,package_root=package_root)
 runtime.require(package.actor.split in ('train','train_policy_development'),'Neutral pilot is TRAIN-only')
 binding=json.loads(runtime.private(binding_path));profile=json.loads(runtime.private(profile_path))
 runtime.require(binding['schema']==runtime.SCHEMA and binding['single_account'] is True and binding['scope']=='existing_account_dedicated_disposable_folder' and binding['max_wall_seconds']==1200 and
  binding['source_sha256s']==runtime.source_hashes(),'Exact original runtime/single-account lease binding required')
 runtime.require(profile['schema']=='office-owned-folder-native-ui-profile-v3' and profile['download_surface']=='folder_toolbar' and profile['folder_inventory_proof']['mode']=='parent_card_count',
  'Observed folder-toolbar and parent-card profile required')
 v4={name:runtime.sha((repo/name).read_bytes()) for name in V4_FILES}
 runtime.require(binding['supplemental_source_sha256s']==v4,'Exact v4 native source map required')
 value={'schema':'office-neutral-lifecycle-pilot-config-v4','repo_root':str(repo),'package_root':str(Path(package_root).resolve()),
  'package_ref':reference(package_descriptor),'binding_ref':reference(binding_path),'profile_ref':reference(profile_path),
  'source_sha256s':source_hashes(repo),'output_root':str(output),'task_id':package.actor.task_id,'package_sha256':package.binding_sha256,
  'account_principal_sha256':binding['account_principal_sha256'],'folder_scope_sha256':binding['folder_scope_sha256'],
  'neutral_control_only':True,'synthetic_finish_not_model':True,'model_calls':0,'provider_calls':0,'official_final_credit':0,
  'native_lifecycle_qualified':False,'raw_strict_baseline_score':package.strict_score(package.paths['baseline'])['score']}
 runtime.write_new(config_path,runtime.canonical(value));return {'status':'neutral_pilot_prepared_no_native_call','config_sha256':runtime.sha(runtime.private(config_path)),'model_calls':0,'provider_calls':0}


def validate(config_path,permit_path=None):
 config=json.loads(runtime.private(config_path));runtime.require(config['schema']=='office-neutral-lifecycle-pilot-config-v4' and config['neutral_control_only'] is True and config['synthetic_finish_not_model'] is True and config['model_calls']==config['provider_calls']==config['official_final_credit']==0,'Exact neutral-only source configuration required')
 repo=Path(config['repo_root']);runtime.require(config['source_sha256s']==source_hashes(repo),'Neutral pilot source changed')
 descriptor,_=read_ref(config['package_ref']);binding_path,binding_raw=read_ref(config['binding_ref']);profile_path,profile_raw=read_ref(config['profile_ref'])
 package=runtime.Package(descriptor,package_root=config['package_root']);binding=json.loads(binding_raw);profile=json.loads(profile_raw)
 runtime.require(package.actor.task_id==config['task_id'] and package.binding_sha256==config['package_sha256'],'Frozen package changed')
 if permit_path is not None:
  permit=json.loads(runtime.private(permit_path));runtime.require(permit.get('schema')=='office-neutral-lifecycle-pilot-permit-v4' and permit.get('config_sha256')==runtime.sha(runtime.private(config_path)) and
   permit.get('root_source_reviewed') is True and permit.get('native_execution_authorized') is True and permit.get('synthetic_neutral_finish_only') is True and permit.get('model_calls_authorized')==0 and
   permit.get('native_lifecycle_qualified') is False,'Explicit reviewed neutral native permit required')
  runtime.require(profile['source_reviewed'] is True and all(v['source_reviewed'] is True and v['open_steps']==[] for v in profile['signed_in_principal'].values()),'Root must approve actual passive principal profiles before native work')
  runtime.require(profile.get('delete_steps') and binding['source_sha256s']==runtime.source_hashes(),'Root must bind exact owned delete/cleanup profile')
 return config,package,binding,profile


def run(*,config_path,permit_path,enable_native=False):
 runtime.require(enable_native is True,'Native neutral pilot disabled')
 config,package,binding,profile=validate(config_path,permit_path)
 output=Path(config['output_root']);runtime.require(not output.exists() and not output.is_symlink(),'Neutral pilot consumed; no replay');output.mkdir(mode=0o700)
 # Approval is copied from the exact human-reviewed permit, never fabricated
 # by preparation. This source admission cannot claim formal qualification.
 admission={'schema':'office-owned-folder-native-host-source-review-v2','approved':True,'single_account':True,'graph_used':False,
  'actual_native_lifecycle_qualified':False,'account_principal_sha256':binding['account_principal_sha256'],'folder_scope_sha256':binding['folder_scope_sha256'],
  'native_evidence_root':binding['native_evidence_root'],'supplemental_source_sha256s':binding['supplemental_source_sha256s'],
  'reviewed_config_sha256':runtime.sha(runtime.private(config_path)),'reviewed_permit_sha256':runtime.sha(runtime.private(permit_path))}
 admission_path=output/'source-admission.private.json';runtime.write_new(admission_path,runtime.canonical(admission))
 native_permit={'schema':'office-owned-folder-runtime-permit-v2','binding_sha256':runtime.sha(runtime.private(config['binding_ref']['path'])),
  'source_reviewed':True,'development_only':True,'reviewed_permit_sha256':runtime.sha(runtime.private(permit_path))}
 native_permit_path=output/'runtime-permit.private.json';runtime.write_new(native_permit_path,runtime.canonical(native_permit))
 spool=NativeOperationSpool(output/'operation-spool.private',source_admission=admission_path)
 client=runtime.Runtime(spool,binding_path=Path(config['binding_ref']['path']),permit_path=native_permit_path,artifact_root=output/'native-episode.private',mode='native_development')
 started=time.monotonic();success=False
 try:
  with client.open(package,attempt_id='neutral-one-use-v4') as active:
   observation=active.observe(memory='')
   action=normalize_model_action('{"type":"finish"}',observation,current_frame_id=active.current_frame_id())
   dispatch=active.dispatch(action);runtime.require(dispatch['status']=='applied','Neutral finish current-frame guard did not accept')
  reset=json.loads(runtime.private(client.root/'reset-score.private.json'))
  runtime.require(reset['equivalent'] is True,'Actual fresh neutral reset missing')
  result={'schema':'office-neutral-lifecycle-pilot-result-v4','status':'native_lifecycle_neutral_control_completed',
   'task_id':package.actor.task_id,'package_sha256':package.binding_sha256,'model_calls':0,'provider_calls':0,'actor_source':'explicit_synthetic_neutral_finish',
   'raw_strict_saved_score':active.saved_score['score'],'fresh_reset_equivalent':True,'lifecycle_wall_seconds':time.monotonic()-started,
   'native_lifecycle_qualified':False,'generic_student_verifier_qualified':False,'official_final_credit':0}
  runtime.write_new(output/'result.private.json',runtime.canonical(result));success=True;return {k:result[k] for k in ('status','model_calls','provider_calls','native_lifecycle_qualified','official_final_credit')}
 finally:
  if not success:runtime.write_new(output/'terminal-retained.private.json',runtime.canonical({'status':'native_lifecycle_failed_or_uncertain_no_replay','model_calls':0,'provider_calls':0,'native_lifecycle_qualified':False,'account_lease_may_be_retained':True}))


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','check','run'))
 parser.add_argument('--config',type=Path,required=True);parser.add_argument('--permit',type=Path);parser.add_argument('--enable-native',action='store_true')
 for name in ('repo-root','package-descriptor','package-root','binding','profile','output'):parser.add_argument('--'+name,type=Path)
 args=parser.parse_args()
 if args.mode=='prepare':result=prepare(repo_root=args.repo_root,package_descriptor=args.package_descriptor,package_root=args.package_root,binding_path=args.binding,profile_path=args.profile,output=args.output,config_path=args.config)
 elif args.mode=='check':validate(args.config,args.permit);result={'status':'neutral_source_inputs_checked_no_native_call','model_calls':0,'provider_calls':0}
 else:result=run(config_path=args.config,permit_path=args.permit,enable_native=args.enable_native)
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
