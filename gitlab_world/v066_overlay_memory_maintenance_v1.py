"""Reviewed, one-use Colima resize preserving existing GitLab COW directories.

Prepare is read-only. Execute is an explicit original-evaluator operation.
It never calls reset.reset, clears an overlay, rewrites COW metadata, removes
a container or touches the original immutable seed contents.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack,contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
from unittest.mock import patch

from . import bootstrap,operators,reset,runtime,verify
from . import v066_prospective_cohort_v5 as source

CORE_FILES=('gitlab_world/runtime.py','gitlab_world/reset.py','gitlab_world/verify.py',
            'gitlab_world/bootstrap.py','gitlab_world/operators.py')
ROLES=('config','logs','data')
SCHEMA='envloop-gitlab-overlay-preserving-memory-maintenance-v1'


def sha(raw):return hashlib.sha256(raw).hexdigest()


def retained_command(argv:list[str], output_root:Path, label:str, timeout:int):
 def retain(suffix,raw):
  if isinstance(raw,str):raw=raw.encode()
  fd=os.open(output_root/(label+suffix),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as stream:stream.write(raw or b'');stream.flush();os.fsync(stream.fileno())
 try:
  result=subprocess.run(argv,capture_output=True,timeout=timeout)
 except subprocess.TimeoutExpired as exc:
  retain('.stdout.private.log',exc.stdout);retain('.stderr.private.log',exc.stderr)
  raise
 retain('.stdout.private.log',result.stdout);retain('.stderr.private.log',result.stderr)
 result.check_returncode()
 return result


@contextmanager
def original_scope(evaluator_root:Path):
 private=evaluator_root/'work/gitlab-full-world';version=(private/'active-volume-version.txt').read_text().strip()
 if version!='v3':raise ValueError('Only preserved original v3 overlay is eligible')
 with ExitStack() as stack:
  for module,fields in ((runtime,{'PRIVATE':private,'ACTIVE_VERSION':version,'VOLUMES':runtime.volume_names(version)}),
                       (bootstrap,{'PRIVATE':private,'PROGRESS_FILE':private/'bootstrap-progress.json'}),
                       (operators,{'PRIVATE':private,'RECEIPT':private/'operator-bootstrap-private.json'})):
   for name,value in fields.items():stack.enter_context(patch.object(module,name,value))
  yield private


def worker_proof(evaluator_root:Path):
 text=subprocess.run(['ps','-axo','pid=,ppid=,command='],capture_output=True,text=True,check=True).stdout
 rows=[];parents={}
 for line in text.splitlines():
  pieces=line.strip().split(maxsplit=2)
  if len(pieces)==3:
   pid,ppid=int(pieces[0]),int(pieces[1]);parents[pid]=ppid;rows.append((pid,ppid,pieces[2]))
 ancestors={os.getpid()};pid=os.getpid()
 while pid in parents and parents[pid] not in ancestors:pid=parents[pid];ancestors.add(pid)
 active=[]
 for pid,ppid,command in rows:
  if pid in ancestors:continue
  if 'gitlab_world.' in command or str(evaluator_root) in command:
   if any(marker in command for marker in ('python','bash','sh ')):
    active.append({'pid':pid,'parent_pid':ppid,'command_sha256':sha(command.encode())})
 if active:raise ValueError('An old or concurrent GitLab worker is live; maintenance refused')
 return {'old_worker_processes':0,'process_snapshot_sha256':sha(text.encode())}


def metadata_hashes(evaluator_root:Path):
 private=evaluator_root/'work/gitlab-full-world'
 return {name:sha((private/name).read_bytes()) for name in source.BOUND_FILES}


def core_hashes(evaluator_root:Path):return {name:sha((evaluator_root/name).read_bytes()) for name in CORE_FILES}


def overlay_recipe(private:Path):
 state=json.loads(source.private(private/'cow-reset-state.json'))
 if state.get('schema')!='envloop-gitlab-overlay-cold-reset-v1':raise ValueError('Original COW schema changed')
 expected=runtime.volume_names('v3');result={}
 for role in ROLES:
  lower='/var/lib/docker/volumes/'+expected[role]+'/_data'
  if state['seed_volume_lowerdirs'][role]!=lower:raise ValueError('Original v3 seed lowerdir changed')
  base='/var/lib/envloop-gitlab-cow-v3/'+role
  result[role]={'lower':lower,'upper':base+'/upper','work':base+'/work','merged':base+'/merged'}
 return result


def vm_readback(recipe:dict):
 # Only metadata/identity is read. No task, database, account or file content
 # is printed by this guest probe.
 script='''import json,os
recipe=PAYLOAD
mounts={}
for line in open('/proc/self/mountinfo'):
 f=line.split();i=f.index('-');mounts[f[4]]={'fstype':f[i+1],'options':f[i+3].split(','),'mount_options':f[5].split(',')}
out={}
for role,paths in recipe.items():
 identities={}
 for kind,path in paths.items():
  st=os.stat(path,follow_symlinks=False)
  if not __import__('stat').S_ISDIR(st.st_mode):raise ValueError('Existing overlay directory missing/not regular directory')
  identities[kind]={'inode':st.st_ino,'mode':st.st_mode & 0o7777,'uid':st.st_uid,'gid':st.st_gid}
 out[role]={'paths':paths,'directories':identities,'mount':mounts.get(paths['merged'])}
print(json.dumps(out,sort_keys=True))
'''.replace('PAYLOAD',repr(recipe))
 return json.loads(reset.vm_shell("python3 - <<'ENVLOOP_MAINTENANCE_PY'\n"+script+"\nENVLOOP_MAINTENANCE_PY",timeout=60))


def verify_mounts(recipe:dict,readback:dict,*,require_mounted=True,expected_directories=None):
 if set(readback)!=set(ROLES):raise ValueError('All three overlay roles must be read back')
 for role in ROLES:
  row=readback[role];paths=recipe[role]
  if row.get('paths')!=paths:raise ValueError('Overlay exact paths changed')
  if expected_directories:
   for kind in ('lower','upper','work'):
    if row['directories'][kind]!=expected_directories[role]['directories'][kind]:raise ValueError('Existing lower/upper/work directory identity changed')
  mount=row.get('mount')
  if require_mounted:
   if type(mount) is not dict or mount.get('fstype')!='overlay' or 'rw' not in mount.get('mount_options',[]):raise ValueError('Exact existing overlay is not mounted read/write')
   options=dict(option.split('=',1) for option in mount['options'] if '=' in option)
   if any(options.get(key)!=paths[field] for key,field in (('lowerdir','lower'),('upperdir','upper'),('workdir','work'))):
    raise ValueError('Overlay lower/upper/work options do not match preserved recipe')
 return True


def seed_identities():
 result={}
 for role,name in runtime.volume_names('v3').items():
  rows=json.loads(runtime.docker('volume','inspect',name))
  if len(rows)!=1 or rows[0].get('Name')!=name:raise ValueError('Original seed volume identity missing')
  result[role]={k:rows[0].get(k) for k in ('Name','Driver','Mountpoint','CreatedAt','Scope')}
 return result


def prepare(*,evaluator_root:Path,plan_path:Path):
 if plan_path.exists() or plan_path.is_symlink():raise ValueError('Exclusive maintenance plan required')
 evaluator_root=evaluator_root.resolve()
 with original_scope(evaluator_root) as private:
  workers=worker_proof(evaluator_root);before=verify.state_snapshot();baseline=json.loads(source.private(private/'baseline-persisted-state.json'))
  if before!=baseline or len(before['project_ids'])!=31:raise ValueError('Original31-project baseline is not exact')
  row=runtime.inspect(runtime.WORLD);proof=runtime.proof(runtime.WORLD)
  if row['HostConfig']['RestartPolicy']['Name']!='no' or proof['running'] is not True or proof['health']!='healthy':
   raise ValueError('Healthy original no-autorestart container required')
  recipe=overlay_recipe(private);mounts=vm_readback(recipe);verify_mounts(recipe,mounts)
  expected_mounts={runtime.DESTS[role]:recipe[role]['merged'] for role in ROLES}
  if {m['Destination']:m['Source'] for m in row['Mounts']}!=expected_mounts:raise ValueError('Original container must bind precisely the three existing overlay mounts')
  info=json.loads(runtime.docker('info','--format','{{json .}}'))
  if not 5*1024**3<info['MemTotal']<7*1024**3 or info['NCPU']!=3:raise ValueError('Maintenance is exactly original6GiB/3CPU to12GiB')
  value={'schema':SCHEMA,'status':'readonly_prepared_original_overlay_resize_not_executed','created_utc':source.now(),
   'evaluator_root':str(evaluator_root),'maintenance_source_sha256':sha(Path(__file__).read_bytes()),'core_source_sha256s':core_hashes(evaluator_root),
   'metadata_sha256s':metadata_hashes(evaluator_root),'original31_snapshot':before,'original_container_id':row['Id'],'original_runtime_proof':proof,
   'original_seed_volume_identities':seed_identities(),'overlay_recipe':recipe,'before_overlay_readback':mounts,'worker_proof':workers,
   'docker_context':runtime.CONTEXT,'colima_profile':'cua-gitlab','cpu':3,'disk_gib':24,'from_memory_gib':6,'to_memory_gib':12,
   'resize_argv':['colima','start','--profile','cua-gitlab','--cpus','3','--memory','12','--disk','24','--activate=false'],
   'reset_reset_called':False,'original_private_cow_or_active_marker_mutation_authorized':False,'model_calls':0,'official_final_admitted':0}
 source.write_new(plan_path,value);return {'status':value['status'],'private_plan_sha256':sha(source.private(plan_path)),'model_calls':0}


def validate(plan_path:Path):
 value=json.loads(source.private(plan_path));root=Path(value['evaluator_root'])
 if value.get('schema')!=SCHEMA or value.get('maintenance_source_sha256')!=sha(Path(__file__).read_bytes()) or core_hashes(root)!=value['core_source_sha256s'] or metadata_hashes(root)!=value['metadata_sha256s']:
  raise ValueError('Reviewed maintenance source or original sealed metadata changed')
 return value


def remount_existing(recipe:dict,expected:dict):
 current=vm_readback(recipe);verify_mounts(recipe,current,require_mounted=False,expected_directories=expected)
 for role in ROLES:
  if current[role]['mount'] is not None:
   verify_mounts({role:recipe[role],**{r:recipe[r] for r in ROLES if r!=role}},current,require_mounted=False,expected_directories=expected)
   options=dict(x.split('=',1) for x in current[role]['mount']['options'] if '=' in x)
   if current[role]['mount']['fstype']!='overlay' or any(options.get(k)!=recipe[role][f] for k,f in (('lowerdir','lower'),('upperdir','upper'),('workdir','work'))):
    raise ValueError('An unexpected mount already occupies the preserved overlay path')
   continue
  paths=recipe[role];options='lowerdir='+paths['lower']+',upperdir='+paths['upper']+',workdir='+paths['work']
  # No mkdir, reset, clear, rm, umount, volume or container recreation.
  reset.vm_shell('mount -t overlay overlay -o '+shlex.quote(options)+' '+shlex.quote(paths['merged']),timeout=60)
 after=vm_readback(recipe);verify_mounts(recipe,after,expected_directories=expected);return after


def execute(*,plan_path:Path,output_root:Path,execute_reviewed:bool=False):
 if execute_reviewed is not True:raise ValueError('Reviewed maintenance execution flag required')
 value=validate(plan_path);evaluator=Path(value['evaluator_root'])
 if Path(__file__).resolve().parents[1]!=evaluator:raise ValueError('Only original evaluator checkout may stop/resize')
 if output_root.exists() or output_root.is_symlink():raise ValueError('Consumed maintenance operation cannot be replayed')
 with original_scope(evaluator):
  worker_proof(evaluator)
  if verify.state_snapshot()!=value['original31_snapshot'] or runtime.inspect(runtime.WORLD)['Id']!=value['original_container_id']:raise ValueError('Original runtime changed after read-only preparation')
  verify_mounts(value['overlay_recipe'],vm_readback(value['overlay_recipe']),expected_directories=value['before_overlay_readback'])
  output_root.mkdir(parents=True,mode=0o700)
  receipt={'schema':SCHEMA,'status':'started','plan_sha256':sha(source.private(plan_path)),'phases':[],
           'original_container_transient_stop':True,'original_never_stopped_claim':False,'reset_reset_called':False,'model_calls':0,'official_final_admitted':0}
  def phase(label):
   receipt['phases'].append({'phase':label,'utc':source.now()});source.persist(output_root/'receipt.private.json',receipt)
  try:
   phase('stop_exact_original_container_gracefully')
   runtime.docker('stop','--time','300',value['original_container_id'],timeout=390)
   stopped=runtime.inspect(runtime.WORLD)
   if stopped['Id']!=value['original_container_id'] or stopped['State']['Running'] or stopped['State'].get('ExitCode')==137:raise ValueError('Original container graceful stop not confirmed')
   phase('preserve_stopped_overlay_directory_identities')
   stopped_mounts=vm_readback(value['overlay_recipe']);verify_mounts(value['overlay_recipe'],stopped_mounts,expected_directories=value['before_overlay_readback'])
   source.write_new(output_root/'stopped-overlay-readback.private.json',stopped_mounts)
   phase('stop_existing_vm_without_force_or_delete')
   retained_command(['colima','stop','--profile','cua-gitlab'],output_root,'colima-stop',300)
   phase('start_same_disk_vm_with12GiB_memory')
   retained_command(value['resize_argv'],output_root,'colima-start',600)
   phase('confirm_original_container_stays_stopped_and_seed_identities_exact')
   stopped=runtime.inspect(runtime.WORLD)
   if stopped['Id']!=value['original_container_id'] or stopped['State']['Running'] or seed_identities()!=value['original_seed_volume_identities']:raise ValueError('Unsafe automatic container restart or changed seed identities')
   phase('remount_exact_existing_overlay_directories')
   mounted=remount_existing(value['overlay_recipe'],stopped_mounts)
   source.write_new(output_root/'remounted-overlay-readback.private.json',mounted)
   phase('start_exact_original_only_after_three_verified_mounts')
   runtime.docker('start',value['original_container_id'],timeout=120);runtime.wait_world()
   phase('independent_exact31_state_metadata_source_seed_check')
   result=verify_operation(plan_path,output_root)
   receipt.update(status='overlay_preserving12GiB_maintenance_independently_verified',verification=result)
  except Exception as exc:
   receipt.update(status='terminal_maintenance_failure_requires_separate_readonly_reconciliation',error_type=type(exc).__name__)
  receipt['finished_utc']=source.now();source.persist(output_root/'receipt.private.json',receipt)
  return {'status':receipt['status'],'private_receipt_sha256':sha(source.private(output_root/'receipt.private.json')),'model_calls':0,'official_final_admitted':0}


def verify_operation(plan_path:Path,output_root:Path):
 value=validate(plan_path);evaluator=Path(value['evaluator_root'])
 with original_scope(evaluator):
  before=json.loads(source.private(output_root/'stopped-overlay-readback.private.json'))
  after=vm_readback(value['overlay_recipe']);verify_mounts(value['overlay_recipe'],after,expected_directories=before)
  proof=runtime.proof(runtime.WORLD)
  if runtime.stable_identity(proof)!=runtime.stable_identity(value['original_runtime_proof']) or proof['running'] is not True or proof['health']!='healthy':raise ValueError('Original exact container identity/health changed')
  if verify.state_snapshot()!=value['original31_snapshot'] or seed_identities()!=value['original_seed_volume_identities']:raise ValueError('Original31 business state or seed volume identities changed')
  info=json.loads(runtime.docker('info','--format','{{json .}}'))
  if not 11*1024**3<info['MemTotal']<13*1024**3 or info['NCPU']!=3:raise ValueError('Expected12GiB/3CPU VM resource readback failed')
  return {'exact31_snapshot':True,'all_original_metadata_sha256s_unchanged':True,'original_metadata_files_checked':len(value['metadata_sha256s']),'core_source_unchanged':True,'seed_volume_identities_unchanged':True,
          'original_container_identity_unchanged':True,'existing_upper_work_directory_identities_unchanged':True,'all_three_exact_overlay_mounts_verified':True,
          'docker_vm_memory_bytes':info['MemTotal'],'cpu':3,'disk_gib':24,'original_transient_stop_recorded':True,
          'cow_generation_and_active_version_unchanged':True,'reset_reset_called':False,'model_calls':0,'official_final_admitted':0}


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','execute','verify'))
 p.add_argument('--evaluator-root',type=Path);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output-root',type=Path)
 p.add_argument('--execute-reviewed-maintenance',action='store_true');a=p.parse_args()
 if a.mode=='prepare':result=prepare(evaluator_root=a.evaluator_root,plan_path=a.plan)
 elif a.mode=='execute':result=execute(plan_path=a.plan,output_root=a.output_root,execute_reviewed=a.execute_reviewed_maintenance)
 else:result=verify_operation(a.plan,a.output_root)
 print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
