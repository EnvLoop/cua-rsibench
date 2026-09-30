"""Clone-scoped FIFO bootstrap,33-project baseline and native ACL proof.

No original container, volume, baseline, credentials or progress is changed.
Reviewed live execution copies immutable seed storage into dedicated volumes
and serves its independent cohort on a separate loopback port.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager,ExitStack
import copy
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
from unittest.mock import patch
from urllib.parse import urlsplit

from . import bootstrap,factory,gui_controls,gui_workflows,operator_acl_probe,operators,reset,runtime,verify
from . import v066_boot_only_probe_v5 as boot
from . import v066_prospective_cohort_v6 as source
from . import v066_prospective_cohort_v5 as parent_source
from . import v066_prospective_cohort_runtime_v5 as parent_scoped
from . import prospective_final_controls_v066 as lane


def closed_control_sources()->dict:
 root=Path(__file__).resolve().parents[1]
 names=tuple(dict.fromkeys(lane.SOURCE_FILES+source.SOURCE_FILES))
 return {name:source.sha((root/name).read_bytes()) for name in names}


def profile_environment(raw:str)->str:
 lines=raw.splitlines();present=[line for line in lines if line.startswith('SVWAIT=')]
 if present and present!=['SVWAIT=60']:raise ValueError('Unknown inherited SVWAIT profile')
 return '\n'.join([line for line in lines if not line.startswith('SVWAIT=')]+['SVWAIT=60'])+'\n'


def profile_binding(root:Path,value:dict)->dict:
 raw=source.private(root/'runtime.env');lines=raw.decode().splitlines()
 if [line for line in lines if line.startswith('SVWAIT=')]!=['SVWAIT=60'] or value.get('startup_profile')!={'SVWAIT':'60','readiness_seconds':900,'supervisor_seconds':7200,'startup_restart_attempts':0}:
  raise ValueError('Exact finite successor startup profile changed')
 return {'runtime_env_sha256':source.sha(raw),'SVWAIT':'60','readiness_seconds':900,'supervisor_seconds':7200,'startup_restart_attempts':0}


def no_old_worker(evaluator_root:Path)->dict:
 text=subprocess.run(['ps','-axo','pid=,ppid=,command='],capture_output=True,text=True,check=True).stdout
 rows=[];parents={}
 for line in text.splitlines():
  fields=line.strip().split(maxsplit=2)
  if len(fields)==3:
   pid,ppid=int(fields[0]),int(fields[1]);parents[pid]=ppid;rows.append((pid,ppid,fields[2]))
 ancestors={os.getpid()};pid=os.getpid()
 while pid in parents and parents[pid] not in ancestors:pid=parents[pid];ancestors.add(pid)
 for pid,ppid,command in rows:
  if pid not in ancestors and ('gitlab_world.' in command or str(evaluator_root) in command) and any(marker in command for marker in ['python','bash','sh ']):
   raise ValueError('Concurrent GitLab worker must terminate before parent archival')
 return {'old_worker_processes':0,'process_snapshot_sha256':source.sha(text.encode())}


def resource_preflight(value:dict)->dict:
 from .v066_prospective_resource_preflight_v5 import preflight
 protected={**value,'original_private_root':value['protected_original_private_root']}
 worker=no_old_worker(Path(value['evaluator_root']))
 result=preflight(protected)  # Original31 remains healthy; measured copy bytes are immutable32 seeds.
 parent=parent_source.validate_source(Path(value['parent_source_freeze_path']))
 with parent_scoped.cohort_context(parent):
  proof=runtime.proof(runtime.WORLD)
  baseline=json.loads(source.private(Path(parent['epoch_root'])/'baseline-persisted-state.json'))
  if proof.get('running') is not True or proof.get('health')!='healthy' or verify.state_snapshot()!=baseline or len(baseline['project_ids'])!=32:
   raise ValueError('Retained v5 parent must be at exact32 baseline before archival')
 result.update(worker_proof=worker,parent32_exact_readback=True,parent_runtime_proof=proof,parent_baseline_business_sha256=baseline['business_sha256'])
 return result


def archive_parent(value:dict,preflight:dict)->dict:
 no_old_worker(Path(value['evaluator_root']))
 parent=parent_source.validate_source(Path(value['parent_source_freeze_path']))
 with parent_scoped.cohort_context(parent):
  current=runtime.proof(runtime.WORLD)
  if current!=preflight['parent_runtime_proof'] or verify.state_snapshot()!=json.loads(source.private(Path(parent['epoch_root'])/'baseline-persisted-state.json')):
   raise ValueError('Parent runtime/baseline changed before graceful archival stop')
  runtime.docker('stop','--time','300',runtime.WORLD,timeout=330)
  stopped=runtime.proof(runtime.WORLD)
  if stopped.get('running') is not False or runtime.stable_identity(stopped)!=runtime.stable_identity(current):
   raise ValueError('Parent archive stop did not preserve exact container identity')
 return {'parent_explicitly_stopped':True,'parent_pre_stop_proof':current,'parent_stopped_proof':stopped,'parent_seed_and_terminal_files_unchanged':True}


def local_url(value:str)->bool:
 parsed=urlsplit(value)
 return ((parsed.scheme=='http' and parsed.hostname in ['127.0.0.1','localhost'] and parsed.port==8018 and
          not parsed.username and not parsed.password) or parsed.scheme in ['about','blob','data'])


def ids_for_progress(path:Path)->list[int]:
 progress=json.loads(source.private(path));projects=progress['projects']
 ids=sorted(int(row['project_id']) for row in projects.values())
 if len(ids) not in [32,33] or len(set(ids))!=len(ids) or any(i<=0 for i in ids) or not all(r.get('complete') is True for r in projects.values()):
  raise ValueError('Clone readback requires complete32/33-project progress')
 return ids


def validate_snapshot(snapshot:dict,expected_count:int)->dict:
 if expected_count not in [32,33] or len(snapshot.get('project_ids',[]))!=expected_count or snapshot.get('schema')!=verify.SCHEMA:
  raise ValueError('Exact prospective readback project count/schema changed')
 value=copy.deepcopy(snapshot);digest=value.pop('business_sha256',None)
 if factory.sha256(factory.canonical(value))!=digest:raise ValueError('Persisted33-project business digest changed')
 counts=verify.counts(snapshot)
 expected={'projects':expected_count,'issues':expected_count*6,'members':expected_count*3,
  'merge_requests':expected_count*2,'projects_with_git_refs':expected_count,'groups':3,'group_members':6,'operators':3,
  'milestones':0,'issue_assignees':0}
 if any(counts.get(k)!=v for k,v in expected.items()) or any(len(row['refs'])!=3 for row in snapshot['git'].values()):
  raise ValueError('Prospective bootstrap DB/Git counts or pristine fields changed')
 if any(row.get('admin') is not False for row in snapshot['db']['operators']) or any(row.get('visibility_level')!=0 for row in snapshot['db']['groups']):
  raise ValueError('Prospective operators/group privacy changed')
 operator_ids={r['id'] for r in snapshot['db']['operators']};group_ids={r['id'] for r in snapshot['db']['groups']}
 scoped=[r for r in snapshot['db']['group_members'] if r['user_id'] in operator_ids]
 if len(scoped)!=3 or {r['source_id'] for r in scoped}!=group_ids or {r['user_id'] for r in scoped}!=operator_ids or any(r['access_level']!=50 for r in scoped):
  raise ValueError('Prospective non-admin one-owner-per-partition ACL changed')
 return {'business_sha256':digest,'project_count':expected_count,'independent_postgresql_git_readback':True,'counts':counts}


def original_projection(snapshot:dict,baseline:dict)->dict:
 ids=set(baseline['project_ids']);issue_ids={r['id'] for r in baseline['db']['issues']}
 output=copy.deepcopy(snapshot);output['project_ids']=baseline['project_ids'];output['git']={str(i):snapshot['git'][str(i)] for i in baseline['project_ids']}
 rules={'projects':lambda r:r['id'] in ids,'issues':lambda r:r['project_id'] in ids,'labels':lambda r:r['project_id'] in ids,
  'members':lambda r:r['source_id'] in ids,'merge_requests':lambda r:r['target_project_id'] in ids,
  'milestones':lambda r:r['project_id'] in ids,'issue_assignees':lambda r:r['issue_id'] in issue_ids,
  'issue_label_links':lambda r:r['target_id'] in issue_ids}
 for table,predicate in rules.items():output['db'][table]=[r for r in snapshot['db'][table] if predicate(r)]
 output.pop('business_sha256',None);output['business_sha256']=factory.sha256(factory.canonical(output))
 return output


@contextmanager
def private_screenshots(root:Path):
 from playwright.async_api import Page
 original=Page.screenshot
 async def owner_only(page,*args,**kwargs):
  name=kwargs.pop('path',None)
  if name is not None:
   path=Path(name).resolve()
   if not path.is_relative_to(root.resolve()) or path.exists():raise ValueError('Screenshot must be a new private cohort file')
  raw=await original(page,*args,**kwargs)
  if name is not None:
   path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
   fd=__import__('os').open(path,__import__('os').O_WRONLY|__import__('os').O_CREAT|__import__('os').O_EXCL,0o600)
   with __import__('os').fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();__import__('os').fsync(stream.fileno())
  return raw
 with patch.object(Page,'screenshot',owner_only):yield


def wait_cohort()->dict:
 deadline=time.monotonic()+900
 while time.monotonic()<deadline:
  inspected=runtime.inspect(runtime.WORLD);state=inspected['State']
  if [item for item in inspected.get('Config',{}).get('Env',[]) if item.startswith('SVWAIT=')]!=['SVWAIT=60']:raise ValueError('Actual clone container startup environment changed')
  if inspected.get('Image')!=runtime.IMAGE_ID:raise ValueError('Pinned GitLab image identity changed')
  if not state.get('Running'):raise RuntimeError('New cohort container exited during boot')
  if state.get('Health',{}).get('Status')=='healthy' and runtime._http_ready():return runtime.proof(runtime.WORLD)
  time.sleep(5)
 raise TimeoutError('New cohort readiness deadline exceeded')


@contextmanager
def cohort_context(value:dict):
 private=Path(value['epoch_root']);progress=private/'bootstrap-progress.json'
 original_reset=reset.reset
 forensic_count=[0]
 def create_case():
  profile_binding(private,value)
  args=['run','-d','--name',runtime.WORLD,'--hostname','gitlab-cohort.local','--restart','no','--env-file',str(private/'runtime.env'),
        '-p','127.0.0.1:8018:8018']
  for role,destination in runtime.DESTS.items():args.extend(['-v',value['clone_vm_root']+'/'+role+'/merged:'+destination])
  args.append(runtime.IMAGE);runtime.docker(*args)
  try:return wait_cohort()
  except Exception:
   capture_forensics(private/'startup-forensics'/('failed-create-'+str(time.monotonic_ns())));raise
 def captured_reset():
  try:return original_reset()
  finally:
   forensic_count[0]+=1;capture_forensics(private/'startup-forensics'/('reset-'+str(time.monotonic_ns())+'-'+str(forensic_count[0])))
 with ExitStack() as stack:
  for module,fields in [
   (runtime,{'PRIVATE':private,'WORLD':value['clone_container_name'],'BASE':'http://127.0.0.1:8018','VOLUMES':value['clone_volume_names'],'ACTIVE_VERSION':'prospective-v6'}),
   (bootstrap,{'PRIVATE':private,'WORLD_FILE':private/'world-private.json','SEED_FILE':private/'world-seed.txt','TOKEN_FILE':private/'bootstrap-token.txt','PROGRESS_FILE':progress}),
   (operators,{'PRIVATE':private,'CREDENTIALS':private/'operator-credentials-private.json','RECEIPT':private/'operator-bootstrap-private.json'}),
   (reset,{'PRIVATE':private,'STATE_FILE':private/'cow-reset-state.json','VM_ROOT':value['clone_vm_root'],'_create_case':create_case,'reset':captured_reset}),
   (operator_acl_probe,{'PRIVATE':private/'native-acl','_local':local_url}),
   (gui_controls,{'PRIVATE':private/'gui-controls','_local_url':local_url}),
   (verify,{'_ids':lambda:ids_for_progress(progress),'verify_bootstrap':lambda snapshot:validate_snapshot(snapshot,len(ids_for_progress(progress)))})]:
   for name,replacement in fields.items():stack.enter_context(patch.object(module,name,replacement))
  if hasattr(gui_workflows,'_local_url'):stack.enter_context(patch.object(gui_workflows,'_local_url',local_url))
  stack.enter_context(patch.object(lane,'source_sha256s',closed_control_sources))
  stack.enter_context(private_screenshots(private));yield


def capture_forensics(folder:Path)->dict:
 folder.mkdir(parents=True,mode=0o700,exist_ok=False)
 return boot.capture_startup_forensics(folder)


def audit_native_acl(root:Path,acl:dict)->dict:
 from io import BytesIO
 from PIL import Image
 if (acl.get('schema')!='envloop-gitlab-prospective33-native-acl-private-v6' or acl.get('operator_count')!=3 or
     acl.get('own_project_successes')!=3 or acl.get('cross_partition_denials')!=6 or
     acl.get('new_fifo_project_in_final_operator_probe') is not True or acl.get('non_admin_actors') is not True):
  raise ValueError('Prospective native ACL aggregate/schema incomplete')
 cases=acl.get('cases');partitions=set(operators.PARTITIONS)
 credentials=json.loads(source.private(root/'operator-credentials-private.json'))
 if type(cases) is not list or len(cases)!=3 or {r.get('partition') for r in cases}!=partitions:
  raise ValueError('Prospective three actual browser ACL cases missing')
 own=cross=0
 for case in cases:
  partition=case['partition']
  if (case.get('fresh_browser_context') is not True or set(case.get('access',{}))!=partitions or
      case.get('user_sha256')!=factory.sha256(credentials[partition]['username'])):
   raise ValueError('Prospective scoped operator/browser identity changed')
  for target,access in case['access'].items():
   allowed=target==partition
   if (access.get('allowed_expected') is not allowed or access.get('native_http_status')!=(200 if allowed else 404) or
       access.get('project_title_visible') is not allowed):raise ValueError('Native project ACL response/title disagrees')
   path=root/'native-acl'/partition/(target+'.png');raw=source.private(path)
   if source.sha(raw)!=access.get('screenshot_sha256'):raise ValueError('Native ACL screenshot bytes changed')
   with Image.open(BytesIO(raw)) as image:
    if image.format!='PNG' or image.size!=(1440,1000):raise ValueError('Native ACL screenshot viewport/format changed')
   own+=int(allowed);cross+=int(not allowed)
 return {'native_browser_cases_reopened':3,'native_acl_pngs_reopened':9,'own_successes':own,'cross_denials':cross}


async def native_acl(value:dict,world:dict,project:dict)->dict:
 from playwright.async_api import async_playwright
 groups=operators.plan(world)['groups']
 projects={partition:next(p for p in bootstrap.all_projects(world) if p['group_path']==group) for partition,group in groups.items()}
 projects['final_candidate_unsealed']=project
 credentials=json.loads(source.private(operators.CREDENTIALS));results=[]
 async with async_playwright() as playwright:
  browser=await playwright.chromium.launch(headless=True)
  try:
   for partition in operators.PARTITIONS:results.append(await operator_acl_probe._case(browser,partition,credentials[partition],projects))
  finally:await browser.close()
 own=sum(r['access'][r['partition']]['native_http_status']==200 for r in results)
 cross=sum(v['native_http_status']==404 for r in results for p,v in r['access'].items() if p!=r['partition'])
 if own!=3 or cross!=6:raise ValueError('New FIFO native own/cross-partition ACL failed')
 return {'schema':'envloop-gitlab-prospective33-native-acl-private-v6','operator_count':3,'own_project_successes':3,'cross_partition_denials':6,
  'new_fifo_project_in_final_operator_probe':True,'non_admin_actors':True,'cases':results,'model_calls':0,'official_final_admitted':0}


def _copy_private(original:Path,new:Path,name:str)->None:
 raw=source.private(original/name);path=new/name;path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
 descriptor=__import__('os').open(path,__import__('os').O_WRONLY|__import__('os').O_CREAT|__import__('os').O_EXCL,0o600)
 with __import__('os').fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();__import__('os').fsync(stream.fileno())


def bootstrap_clone(*,freeze_path:Path,permit_path:Path|None,execute:bool=False)->dict:
 if execute is not True:raise ValueError('Live clone bootstrap requires explicit reviewed execution')
 from .v066_prospective_cohort_controller_v6 import checked_permit,freeze_baseline_plan
 value=source.validate_source(freeze_path)
 if permit_path is None:raise ValueError('Exact independent bootstrap permit required')
 checked_permit(freeze_path=freeze_path,permit_path=permit_path,value=value,phase='bootstrap')
 if Path(__file__).resolve().parents[1]!=Path(value['evaluator_root']):raise ValueError('Only original evaluator checkout may execute live cohort mutation')
 root=Path(value['epoch_root']);original=Path(value['original_private_root'])
 if root.exists() or root.is_symlink():raise ValueError('Consumed bootstrap epoch cannot be replayed')
 resource=resource_preflight(value)  # Read-only refusal occurs before the bootstrap intent.
 root.mkdir(mode=0o700)
 source.write_new(root/'resource-preflight.private.json',resource)
 source.write_new(root/'bootstrap-intent.private.json',{'schema':'envloop-gitlab-prospective-bootstrap-intent-v6','freeze_sha256':source.sha(source.private(freeze_path)),
  'permit_sha256':source.sha(source.private(permit_path)),'created_utc':source.now(),'one_new_fifo_project':True,'same_intent_replay_authorized':False,'model_calls':0,'official_final_admitted':0})
 receipt={'schema':'envloop-gitlab-prospective-bootstrap-receipt-private-v6','status':'started','freeze_sha256':source.sha(source.private(freeze_path)),
  'phase_times':[],'same_intent_replay_authorized':False,'model_calls':0,'official_final_admitted':0}
 def phase(name):receipt['phase_times'].append({'phase':name,'utc':source.now(),'monotonic_ns':time.monotonic_ns()});source.persist(root/'bootstrap-receipt.private.json',receipt)
 original_container=runtime.WORLD;before_original=None
 try:
  phase('validate_original_runtime_readonly');before_original=runtime.proof(original_container)
  phase('copy_private_fixture_authority_into_new_epoch')
  for name in ['bootstrap-progress.json','operator-bootstrap-private.json','operator-credentials-private.json','world-seed.txt','runtime.env']:_copy_private(original,root,name)
  if (original/'bootstrap-token.txt').exists():_copy_private(original,root,'bootstrap-token.txt')
  env=profile_environment((root/'runtime.env').read_text().replace('http://127.0.0.1:8016','http://127.0.0.1:8018').replace("nginx['listen_port'] = 8016","nginx['listen_port'] = 8018"))
  (root/'runtime.env').write_text(env);(root/'runtime.env').chmod(0o600)
  recipe=json.loads(source.private(Path(value['recipe_path'])))
  # Trusted live fixture setup is the first place full task records are loaded.
  world=json.loads(source.private(original/'world-private.json'));new_tasks=factory._tasks(recipe['project'])
  if [source.sha(factory.canonical(t)) for t in new_tasks]!=[t['task_object_sha256'] for t in recipe['task_metadata']]:raise ValueError('Live task materialization differs from FIFO commitment')
  world['reserve_projects'].append(recipe['project']);world['reserve_tasks'].extend(new_tasks)
  source.write_new(root/'world-private.json',world)
  phase('copy_original_seed_through_read_only_bind_mounts')
  runtime.docker('info','--format','{{json .ServerVersion}}')
  for role,volume in value['clone_volume_names'].items():
   try:runtime.docker('volume','inspect',volume)
   except subprocess.CalledProcessError:pass
   else:raise ValueError('Prospective volume already exists; no reuse')
   runtime.docker('volume','create',volume)
   lower=value['original_seed_lowerdirs'][role];readonly=value['clone_vm_root']+'/readonly-'+role
   target='/var/lib/docker/volumes/'+volume+'/_data'
   script='set -eu; mkdir -p '+shlex.quote(readonly)+'; mount --bind '+shlex.quote(lower)+' '+shlex.quote(readonly)+'; mount -o remount,bind,ro '+shlex.quote(readonly)+'; cp -a '+shlex.quote(readonly+'/.')+' '+shlex.quote(target+'/')+'; umount '+shlex.quote(readonly)
   reset.vm_shell(script,timeout=900)
  copied_config='/var/lib/docker/volumes/'+value['clone_volume_names']['config']+'/_data/gitlab.rb'
  config="external_url 'http://127.0.0.1:8018'; nginx['listen_port'] = 8018; letsencrypt['enable'] = false"
  reset.vm_shell("printf '%s\\n' "+shlex.quote(config)+' >> '+shlex.quote(copied_config),timeout=30)
  phase('explicitly_archive_terminal_v5_parent_runtime')
  archive=archive_parent(value,resource);source.write_new(root/'parent-archive-stop.private.json',archive)
  receipt['parent_archive_stop_sha256']=source.sha(source.private(root/'parent-archive-stop.private.json'))
  with cohort_context(value):
   phase('start_new_clone_on_separate_loopback_port')
   args=['run','-d','--name',runtime.WORLD,'--hostname','gitlab-cohort.local','--restart','no','--env-file',str(root/'runtime.env'),'-p','127.0.0.1:8018:8018']
   for role,destination in runtime.DESTS.items():args.extend(['-v',value['clone_volume_names'][role]+':'+destination])
   args.append(runtime.IMAGE);runtime.docker(*args);wait_cohort()
   old_baseline=json.loads(source.private(original/'baseline-persisted-state.json'));current=verify.state_snapshot()
   if current!=old_baseline:raise ValueError('Copied32-project seed differs before FIFO bootstrap')
   phase('seed_exact_second_fifo_project_only')
   progress=json.loads(source.private(root/'bootstrap-progress.json'))
   bootstrap._seed_one(bootstrap.GitLabAPI(bootstrap.api_token()),recipe['project'],progress)
   after=verify.state_snapshot();validate_snapshot(after,33)
   if original_projection(after,old_baseline)!=old_baseline:raise ValueError('FIFO bootstrap altered original32-project monitored state')
   source.write_new(root/'baseline-persisted-state.json',after)
   phase('native_scoped_operator_acl_readback')
   acl=asyncio.run(native_acl(value,world,recipe['project']));acl_sha=source.write_new(root/'native-acl.private.json',acl)
   phase('freeze_new33_project_immutable_seed_and_exact_cold_clone')
   frozen=reset.freeze();cold=verify.state_snapshot()
   if cold!=after or frozen.get('same_business_sha256') is not True:raise ValueError('New baseline first cold clone mismatch')
   source.write_new(root/'first-cold-readback.private.json',cold)
   plan=freeze_baseline_plan(value=value,freeze_path=freeze_path,baseline=after,acl_sha=acl_sha,world=world)
   receipt['startup_profile_binding']=profile_binding(root,value)
   receipt.update(status='new33_project_fifo_baseline_acl_exact_cold_clone_frozen',baseline_business_sha256=after['business_sha256'],
    baseline_sha256=source.sha(source.private(root/'baseline-persisted-state.json')),acl_sha256=acl_sha,cohort_plan_sha256=plan['plan_sha256'],
    original32_project_projection_unchanged=True,new_project_count=33,prospective_tasks=100,first_cold_clone_exact=True)
  after_original=runtime.proof(original_container)
  if before_original!=after_original:raise ValueError('Original runtime identity/state changed')
  receipt['original_runtime_unmodified']=True
 except Exception as exc:
  receipt['status']='terminal_bootstrap_failure_no_replay';receipt['error_type']=type(exc).__name__
  try:
   with cohort_context(value):receipt['forensics']=capture_forensics(root/'startup-forensics'/('bootstrap-terminal-'+str(time.monotonic_ns())))
  except Exception as forensic:receipt['forensic_error_type']=type(forensic).__name__
 receipt['finished_utc']=source.now();source.persist(root/'bootstrap-receipt.private.json',receipt)
 return {'status':receipt['status'],'private_receipt_sha256':source.sha(source.private(root/'bootstrap-receipt.private.json')),
  'model_calls':0,'official_final_admitted':0}
