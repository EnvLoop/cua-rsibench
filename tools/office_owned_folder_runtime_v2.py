"""Generic single-account, owned-folder Office task runtime.

The actor receives only visible instructions and an owned document. UI host
operations must retain native evidence; scoring runs independently on owner
same-item double-downloads. No Graph or account creation is performed here.
"""
from __future__ import annotations
import argparse,hashlib,json,os,re,secrets,subprocess,sys,tempfile,time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from ppt_wdi_factory import verify as ppt_verify,plan as ppt_plan
from tools import office_single_account_train_pilot_v1 as manual
from cursibench import native_surface_guard_policy_v1 as safety

SCHEMA='office-owned-folder-runtime-v2'
CELLS={'powerpoint-web':'.pptx','excel-web':'.xlsx'}
SOURCE_FILES=('tools/office_owned_folder_runtime_v2.py','tools/office_owned_folder_spool_v2.py','tools/office_owned_folder_native_guard_v2.py','tools/office_owned_folder_cua_host_v2.mjs','tools/office_owned_folder_native_extractor_v2.mjs','tools/office_owned_folder_native_profile_v2.mjs','tools/office_owned_folder_ui_lifecycle_v2.mjs','tools/office_owned_folder_cua_pump_v2.mjs','tools/office_owned_folder_workers_v2.py','tools/office_owned_folder_paid_sampler_v2.py','native_desktop_factory/deadline_model_transport_v21.py','native_desktop_factory/actor_deadline_future_v21.py','native_desktop_factory/uniform_model_transport_v11.py','native_desktop_factory/qwen_sampler_process_v21.py','src/cursibench/scale_vision_proxy.py','tools/office_local_browser_train_bridge_v1.mjs','ppt_wdi_factory/verify.py','ppt_wdi_factory/plan.py','tools/office_single_account_train_pilot_v1.py','src/cursibench/native_surface_guard_policy_v1.py','src/cursibench/scale_action_contract.py','src/cursibench/scale_action_contract_v066.py','tools/sec_excel_web_train_oracle_v1.py','sec_excel_factory/verify_integrated_candidate.py')
SPLITS={'train','train_policy_development','selection','final_candidate','final_candidate_unsealed'}

class OfficeRuntimeError(ValueError):pass

def require(ok,code):
 if not ok:raise OfficeRuntimeError(code)

def sha(raw):return hashlib.sha256(raw).hexdigest()

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def write_new(path,raw):
 path=Path(path);require(path.parent.is_dir() and not path.parent.is_symlink() and not path.parent.stat().st_mode&0o077,'Private output root required')
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 return {'path':path.name,'sha256':sha(raw)}

def private(path):
 path=Path(path);require(path.is_file() and not path.is_symlink() and not path.stat().st_mode&0o077 and path.stat().st_size<=50_000_000,'Private regular package/evidence required')
 return path.read_bytes()

def source_hashes():
 root=Path(__file__).resolve().parents[1]
 return {name:sha((root/name).read_bytes()) for name in SOURCE_FILES}

class AccountLease:
 def __init__(self,account_sha256,*,expires_at_ms,root=None):
  require(re.fullmatch('[a-f0-9]{64}',account_sha256),'Account principal hash invalid')
  self.root=Path(root or tempfile.gettempdir())/'envloop-office-account-leases-v1.private';self.root.mkdir(mode=0o700,exist_ok=True)
  require(not self.root.is_symlink() and not self.root.stat().st_mode&0o077 and self.root.stat().st_uid==os.getuid(),'Shared account lease store unsafe')
  self.path=self.root/('account-'+account_sha256+'.lease.private.json');self.token=secrets.token_hex(16);self.expires_at_ms=expires_at_ms
 def acquire(self):
  try:write_new(self.path,canonical({'token':self.token,'expires_at_ms':self.expires_at_ms}))
  except FileExistsError:raise OfficeRuntimeError('Account already leased; no automatic lease stealing') from None
 def active(self):
  try:value=json.loads(private(self.path))
  except (OSError,ValueError):return False
  return value.get('token')==self.token and value.get('expires_at_ms')==self.expires_at_ms and int(time.time()*1000)<self.expires_at_ms
 def release(self):
  value=json.loads(private(self.path));require(value.get('token')==self.token,'Account lease ownership changed; preserve unknown handle');self.path.unlink()


@dataclass(frozen=True)
class ActorTask:
 task_id:str
 package_sha256:str
 cell_id:str
 split:str
 visible_instruction:str
 baseline_sha256:str

class Package:
 """Visible actor projection and sealed evaluator package stay separate."""
 def __init__(self,descriptor,*,package_root):
  root=Path(package_root).resolve();require(root.is_dir() and not root.is_symlink(),'Task package root missing')
  raw=private(descriptor);value=json.loads(raw)
  require(type(value) is dict and value.get('schema')=='office-owned-folder-task-package-v2' and value.get('cell_id') in CELLS and value.get('split') in SPLITS,
   'Office package cell/split/schema invalid')
  require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',value.get('task_id','')),'Generic task identity invalid')
  self.root,self.value,self.descriptor=root,value,Path(descriptor);self.paths={}
  for role,ref in value['refs'].items():
   require(type(ref) is dict and set(ref)=={'path','sha256'} and not Path(ref['path']).is_absolute() and '..' not in Path(ref['path']).parts,'Package reference escaped root')
   path=root/ref['path'];require(path.resolve().is_relative_to(root),'Package reference escaped root')
   require(sha(private(path))==ref['sha256'],'Frozen task artifact changed');self.paths[role]=path
  require({'baseline','task_spec'}<=set(self.paths) and self.paths['baseline'].suffix==CELLS[value['cell_id']],'Task baseline/spec missing')
  self.binding_sha256=sha(raw);self.task=json.loads(private(self.paths['task_spec']))
  require(self.task.get('task_id')==value['task_id'] or value['cell_id']=='excel-web','Task spec identity changed')
  self.actor=ActorTask(value['task_id'],self.binding_sha256,value['cell_id'],value['split'],value['visible_instruction'],value['refs']['baseline']['sha256'])
  if value['cell_id']=='powerpoint-web':
   for name in ['source-snapshot.private.json','source-provenance.private.json','source-country.private.zip']:
    if (self.paths['baseline'].parent/name).exists():require(name in self.paths,'Source context must be hash-bound in evaluator package')
   require(value['visible_instruction']==self.task['actor_task'],'Actor instruction differs from frozen public task projection')
   self.oracle=ppt_verify.freeze(self.paths['baseline'],self.task)
  else:
   require('case_manifest' in self.paths and value.get('case_id') is not None,'SEC case manifest required')
   from tools.sec_excel_web_train_oracle_v1 import sec_verify
   self.oracle=None
 def actor_projection(self):return dict(self.actor.__dict__)
 def revalidate(self):
  require(sha(private(self.descriptor))==self.binding_sha256,'Evaluator descriptor changed')
  for role,path in self.paths.items():require(sha(private(path))==self.value['refs'][role]['sha256'],'Evaluator/source artifact changed')
 def strict_score(self,candidate):
  self.revalidate()
  if self.value['cell_id']=='powerpoint-web':
   result=ppt_verify.verify(self.paths['baseline'],Path(candidate),self.oracle)
   return {'score':result.get('score'),'raw_strict':result,'native_metadata_normalization_applied':False}
  from tools.sec_excel_web_train_oracle_v1 import sec_verify
  rows=json.loads(private(self.paths['case_manifest']));matches=[r for r in rows if r['case_id']==self.value['case_id']]
  require(len(matches)==1,'SEC case identity not unique')
  result=sec_verify(Path(candidate),self.paths['baseline'],matches[0])
  return {'score':1.0 if result['pass'] else 0.0,'raw_strict':result,'native_metadata_normalization_applied':False,'native_recalculation_verified':False}
 def neutral(self,candidate):
  self.revalidate()
  if self.value['cell_id']=='powerpoint-web':
   result=manual.semantic_source_equal(self.paths['baseline'],Path(candidate))
   return {'equivalent':result.get('slide_text_equal') is True and result.get('embedded_workbook_members_equal') is True and result.get('native_chart_cache_semantically_equal') is True,'material':result}
  from tools.sec_excel_web_train_oracle_v1 import neutral
  return neutral(self.paths['baseline'],Path(candidate))

class NativeHost(Protocol):
 """Evaluator-only UI operations; actor cannot call upload/export/delete."""
 def capabilities(self)->dict:...
 def owned_folder_inventory(self)->dict:...
 def create_from_baseline(self,actor_task:dict,baseline:Path,*,purpose:str)->dict:...
 def double_download(self,item:dict,*,purpose:str)->dict:...
 def actor_open(self,item:dict,actor_task:dict,artifact_root:Path,*,account_lease):...
 def close_document(self,item:dict)->dict:...
 def remove_owned_item(self,item:dict)->dict:...


def validate_native_record(value,*,operation,account,folder):
 require(type(value) is dict and value.get('schema')=='office-owned-folder-native-operation-v2' and value.get('operation')==operation and
  value.get('account_principal_sha256')==account and value.get('folder_scope_sha256')==folder and value.get('native_ui') is True and
  value.get('graph_used') is False and value.get('new_account_used') is False and value.get('status')=='completed',
  'Native owned-folder operation/source scope not proved')
 refs=value.get('raw_refs');require(type(refs) is list and len(refs)>=2,'Actual native UI evidence required')
 return value

class Runtime:
 def __init__(self,host,*,binding_path,permit_path,artifact_root,mode='native'):
  self.host,self.root=host,Path(artifact_root);self.mode=mode;self.root.mkdir(mode=0o700,exist_ok=False)
  self.binding=json.loads(private(binding_path));self.permit=json.loads(private(permit_path));self.sequence=0
  require(self.binding.get('schema')==SCHEMA and self.permit.get('schema')=='office-owned-folder-runtime-permit-v2' and
   self.permit.get('binding_sha256')==sha(private(binding_path)) and self.permit.get('source_reviewed') is True and
   self.binding.get('single_account') is True and self.binding.get('scope')=='existing_account_dedicated_disposable_folder',
   'Exact single-account source/plan review required')
  require(self.binding.get('source_sha256s')==source_hashes(),'Office runtime source closure changed')
  require(self.binding.get('native_policy_sha256')==safety.POLICY_SHA,'Shared native safety policy changed')
  caps=host.capabilities();require(caps.get('surface')=='original-office-web' and caps.get('same_account') is True and caps.get('graph') is False,
   'Original Office single-account UI host required')
  if mode=='native':require(caps.get('qualified_native_operations') is True,'Native lifecycle driver remains unqualified')
  elif mode=='native_development':require(caps.get('native_operations_source_reviewed') is True and self.permit.get('development_only') is True,'Development native source/one-case review required')
  else:require(mode=='offline_fixture' and caps.get('offline_fixture') is True,'Fixture mode cannot control native account')
 def retain(self,operation,record):
  require(not hasattr(self,'account_lease') or self.account_lease.active(),'Shared account lease inactive or changed')
  validate_native_record(record,operation=operation,account=self.binding['account_principal_sha256'],folder=self.binding['folder_scope_sha256'])
  # Every UI evidence ref is reopened; booleans are never the sole authority.
  evidence_root=Path(self.binding['native_evidence_root']).resolve()
  for ref in record['raw_refs']:
   require(set(ref)=={'path','sha256'} and not Path(ref['path']).is_absolute() and '..' not in Path(ref['path']).parts,'Native operation ref escaped root')
   path=evidence_root/ref['path'];require(path.resolve().is_relative_to(evidence_root) and sha(private(path))==ref['sha256'],'Native UI evidence bytes changed')
  write_new(self.root/f'operation-{self.sequence:03d}-{operation}.private.json',canonical(record));self.sequence+=1
  return record
 def inventory(self):return self.retain('folder_inventory',self.host.owned_folder_inventory())
 def downloads(self,item,purpose):
  record=self.retain('double_download',self.host.double_download(item,purpose=purpose));require(record.get('item_identity_sha256')==item['item_identity_sha256'],'Download switched owned item')
  root=Path(self.binding['native_evidence_root']).resolve();refs=record['download_refs'];require(len(refs)==2,'Two actual owner downloads required')
  require(all(type(ref) is dict and set(ref)=={'path','sha256'} and not Path(ref['path']).is_absolute() and '..' not in Path(ref['path']).parts for ref in refs),'Owner download ref escaped scope')
  paths=[root/ref['path'] for ref in refs];require(all(p.resolve().is_relative_to(root) for p in paths),'Owner download ref escaped scope');raw=[private(p) for p in paths]
  require(all(sha(data)==ref['sha256'] for data,ref in zip(raw,refs)) and raw[0]==raw[1],'Saved Office artifact did not stabilize')
  return paths[0],record
 @contextmanager
 def open(self,package:Package,*,attempt_id:str):
  require(package.actor.cell_id in self.binding['cells'] and package.actor.split in self.binding['splits'],'Task outside reviewed Office namespace')
  require(re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',attempt_id),'Attempt identity invalid')
  write_new(self.root/'attempt-intent.private.json',canonical({'attempt_id':attempt_id,'task_id':package.actor.task_id,'package_sha256':package.binding_sha256,'one_use':True}))
  lease=AccountLease(self.binding['account_principal_sha256'],expires_at_ms=int(time.time()*1000)+self.binding['max_wall_seconds']*1000)
  lease.acquire();self.account_lease=lease
  item=None;reset_item=None;initial_empty=False;creation_attempted=False;reset_attempted=False
  try:
   before=self.inventory();require(before['items']==[],'Owned task folder must start empty');initial_empty=True
   creation_attempted=True
   created=self.retain('create_document',self.host.create_from_baseline(package.actor_projection(),package.paths['baseline'],purpose='actor'))
   item=created['item'];require(item['account_principal_sha256']==self.binding['account_principal_sha256'] and item['folder_scope_sha256']==self.binding['folder_scope_sha256'],
    'Created document outside leased account/folder')
   baseline,_=self.downloads(item,'before_actor');require(package.neutral(baseline)['equivalent'],'Native initial artifact is not source neutral')
   self.native_before_sha256=sha(private(baseline));write_new(self.root/'native-before.private.json',canonical({'task_id':package.actor.task_id,'package_sha256':package.binding_sha256,'native_before_sha256':self.native_before_sha256,'item_identity_sha256':item['item_identity_sha256']}))
   active=self.host.actor_open(item,package.actor_projection(),self.root/'actor-private',account_lease=lease)
   require(getattr(active,'native_policy_sha256',None)==safety.POLICY_SHA,'Actor bypassed shared native safety')
   session=Session(self,active,item,package,baseline)
   yield session
   saved,_=self.downloads(item,'saved_actor');score=package.strict_score(saved)
   write_new(self.root/'saved-state-score.private.json',canonical(score));session.saved_score=score
  finally:
   # Every cleanup operation is one-use. An unknown create/delete result keeps
   # the shared account lease and raw handle; it is never replayed or guessed.
   cleanup_error=None
   try:
    if item is not None:
     self.retain('close_document',self.host.close_document(item))
     self.retain('remove_document',self.host.remove_owned_item(item))
    if creation_attempted and item is None:
     raise OfficeRuntimeError('Document creation uncertain; preserve native handle and account lease')
    if initial_empty:
     clean=self.inventory();require(clean['items']==[],'Owned task item/tab was not removed')
     reset_attempted=True
     reset_record=self.retain('create_document',self.host.create_from_baseline(package.actor_projection(),package.paths['baseline'],purpose='reset'))
     reset_item=reset_record['item']
     require(reset_item['account_principal_sha256']==self.binding['account_principal_sha256'] and reset_item['folder_scope_sha256']==self.binding['folder_scope_sha256'],'Reset document outside leased scope')
     reset_file,_=self.downloads(reset_item,'fresh_reset')
     neutral=package.neutral(reset_file);require(neutral['equivalent'],'Fresh native Office reset differs from source')
     write_new(self.root/'reset-score.private.json',canonical(neutral))
   except BaseException as error:
    cleanup_error=error
   finally:
    try:
     if reset_item is not None:
      self.retain('close_document',self.host.close_document(reset_item))
      self.retain('remove_document',self.host.remove_owned_item(reset_item))
     if reset_attempted and reset_item is None:
      raise OfficeRuntimeError('Reset creation uncertain; preserve native handle and account lease')
     if initial_empty:
      require(self.inventory()['items']==[],'Owned folder not empty after reset')
     # A failed initial scope read may hide an outstanding native operation;
     # release only after a known empty scope or a known pre-existing item read.
     if initial_empty and not (creation_attempted and item is None) and not (reset_attempted and reset_item is None):
      lease.release()
     elif not creation_attempted and 'before' in locals():
      lease.release()
    except BaseException as error:
     cleanup_error=cleanup_error or error
   if cleanup_error:
    write_new(self.root/'cleanup-terminal.private.json',canonical({'status':'failed_no_retry','error_class':type(cleanup_error).__name__,'account_lease_retained':lease.path.exists(),'official_final_credit':0}))
    raise cleanup_error

class Session:
 def __init__(self,runtime,actor,item,package,baseline):self.runtime,self.actor,self.item,self.package,self.baseline=runtime,actor,item,package,baseline;self.saved_score=None
 def observe(self,**kwargs):return self.actor.observe(**kwargs)
 def current_frame_id(self):return self.actor.current_frame_id()
 def dispatch(self,action):return self.actor.dispatch(action)
 def reject_model_output(self,text):return self.actor.reject_model_output(text)
 def read_saved_state(self):
  saved,_=self.runtime.downloads(self.item,'explicit_saved_readback');score=self.package.strict_score(saved)
  write_new(self.runtime.root/'explicit-saved-score.private.json',canonical(score));return score


def descriptor(*,cell_id,split,task_id,instruction,baseline,task_spec,out,extra_refs=None,case_id=None):
 require(cell_id in CELLS and split in SPLITS,'Descriptor cell/split invalid')
 root=out.parent;refs={}
 extra_refs=dict(extra_refs or {})
 for name in ['source-snapshot.private.json','source-provenance.private.json','source-country.private.zip']:
  context=Path(baseline).parent/name
  if context.exists():extra_refs[name]=context
 for name,path in {'baseline':Path(baseline),'task_spec':Path(task_spec),**(extra_refs or {})}.items():
  require(path.resolve().is_relative_to(root.resolve()),'Evaluator package references must be beneath descriptor root')
  refs[name]={'path':str(path.relative_to(root)),'sha256':sha(private(path))}
 value={'schema':'office-owned-folder-task-package-v2','cell_id':cell_id,'split':split,'task_id':task_id,'visible_instruction':instruction,
  'refs':refs,'case_id':case_id,'actor_sees_correct_or_oracle':False,'official_final_credit':0}
 return write_new(out,canonical(value))

def main():
 parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
 prep=sub.add_parser('prepare-train');prep.add_argument('--package',type=Path,required=True);prep.add_argument('--out',type=Path,required=True)
 replay=sub.add_parser('replay');replay.add_argument('--descriptor',type=Path,required=True);replay.add_argument('--package-root',type=Path,required=True);replay.add_argument('--candidate',type=Path,required=True)
 sub.add_parser('source-closure');args=parser.parse_args()
 if args.command=='source-closure':print(json.dumps({'schema':SCHEMA,'source_sha256s':source_hashes(),'native_policy_sha256':safety.POLICY_SHA},sort_keys=True));return
 if args.command=='prepare-train':
  import shutil
  task=json.loads(private(args.package/'task.private.json'));require(task.get('split') in ['train','train_policy_development'],'Only TRAIN packages may be prepared by this development command')
  args.out.mkdir(mode=0o700,exist_ok=False)
  for name in ['source.pptx','task.private.json','source-snapshot.private.json','source-provenance.private.json','source-country.private.zip']:
   path=args.package/name
   if path.exists():write_new(args.out/name,private(path))
  ref=descriptor(cell_id='powerpoint-web',split=task['split'],task_id=task['task_id'],instruction=task['actor_task'],baseline=args.out/'source.pptx',task_spec=args.out/'task.private.json',out=args.out/'package.private.json')
  package=Package(args.out/'package.private.json',package_root=args.out)
  print(json.dumps({'schema':SCHEMA,'package_sha256':ref['sha256'],'raw_strict_baseline_score':package.strict_score(package.paths['baseline'])['score'],'native_calls':0,'official_final_credit':0},sort_keys=True));return
 package=Package(args.descriptor,package_root=args.package_root);score=package.strict_score(args.candidate)
 print(json.dumps({'schema':SCHEMA,'raw_strict_score':score['score'],'native_metadata_normalization_applied':False,'native_calls':0,'official_final_credit':0},sort_keys=True))

if __name__=='__main__':main()
