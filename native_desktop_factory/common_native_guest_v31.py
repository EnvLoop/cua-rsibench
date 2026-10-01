"""One concrete offline-bootstrap/native-reader guest for all Desktop actors.

Construction is offline. Formal create requires independently reopened fresh
native qualification. A reviewed development probe may wrap its already-owned
raw guest without authorizing another create or granting task credit.
"""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import time
from .semantic_native_transport_v23 import *
from . import semantic_native_transport_v23 as previous
from . import native_atspi_bootstrap_v25 as bootstrap
from . import native_atspi_epoch_v25 as supplemental
from . import native_visible_surface_probe_v31 as reader

PROBE_SOURCE=Path(__file__).with_name('native_visible_surface_probe_v31.py')
PROBE_SCHEMA=reader.SCHEMA
REMOTE='/tmp/envloop-native-common-v31'
PROBE_PATH=REMOTE+'/native_visible_surface_probe_v31.py'
ACTOR_PATHS=('teacher','control','shared-base','astra','sol56','sol6','luna6')
_CURRENT=ContextVar('envloop_native_common_v31_factory',default=None)
PEERS=('native_accessibility_probe_v23.py','native_accessibility_probe_v24.py','native_visible_surface_probe_v27.py','native_visible_surface_probe_v30.py','native_visible_surface_probe_v31.py')
NEW_SOURCES=('native_desktop_factory/common_native_guest_v31.py','native_desktop_factory/common_native_episode_v31.py','native_desktop_factory/native_visible_surface_probe_v30.py','native_desktop_factory/native_visible_surface_probe_v31.py',
 'tests/test_native_desktop_common_native_guest_v31.py','tests/test_native_desktop_visible_surface_probe_v30.py','tests/test_native_desktop_visible_surface_probe_v31.py')

def source_manifest(root=None):
 from .semantic_native_epoch_v23 import proposal
 root=Path(root or Path(__file__).resolve().parents[1]);sources={**proposal(root)['source_sha256s'],**supplemental.proposal(root)['source_sha256s']}
 for name in (*NEW_SOURCES,'native_desktop_factory/native_visible_surface_probe_v27.py'):
  sources[name]=digest((root/name).read_bytes())
 return {'schema':'cua-native-common-guest-source-v31','source_sha256s':sources,'native_policy_sha256':POLICY_SHA,'actor_paths':list(ACTOR_PATHS),
  'task_policy':{'max_actions':90,'actor_seconds':720,'lease_seconds':1200},'offline_bootstrap_before_prepare':True,'child_gi_typelib_path':bootstrap.PREFIX,
  'base_and_supplemental_content_attestation_required':True,'native_reader_schema':PROBE_SCHEMA,'old_results_reclassified':False,'native_qualification_passed':False}

def exclusive(path,raw):
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as file:file.write(raw);file.flush();os.fsync(file.fileno())

def checked_runtime_manifest(value,root):
 current=source_manifest(root)
 require(value==current,'Frozen common native source manifest changed')
 return current

class CommonNativeModelGuest(previous.SemanticModelGuest):
 def __init__(self,*args,native_manifest,source_root=None,**kwargs):
  self.source_root=Path(source_root or Path(__file__).resolve().parents[1]);self.native_manifest=checked_runtime_manifest(native_manifest,self.source_root)
  self.native_manifest_sha256=digest(canonical(self.native_manifest));self.requested_points=[];self.last_native_point=None;self.bootstrap_completed=False
  super().__init__(*args,**kwargs)
 def _command(self,name,command,*,timeout,request_timeout):
  result=self.sandbox.commands.run(command,timeout=timeout,request_timeout=request_timeout)
  json_put(self.root,self.out/(name+'.private.json'),{'exit_code':result.exit_code,'stdout':result.stdout,'stderr':result.stderr,'command_sha256':digest(command.encode()),'native_source_manifest_sha256':self.native_manifest_sha256})
  require(result.exit_code==0,'Common native trusted setup command failed');return result
 def _bootstrap(self):
  require(not self.bootstrap_completed,'Common native bootstrap is one-use')
  # This exclusive namespace is checked before any copy, task open or profile
  # preparation; it cannot adopt a prior guest bootstrap.
  self._command('native-bootstrap-setup','mkdir -m 700 '+shlex.quote(REMOTE),timeout=5,request_timeout=12)
  for name in PEERS:
   relative='native_desktop_factory/'+name;raw=(self.source_root/relative).read_bytes();require(digest(raw)==self.native_manifest['source_sha256s'][relative],'Native peer changed before copy')
   self.sandbox.files.write(REMOTE+'/'+name,raw)
  code=(self.source_root/'native_desktop_factory/native_atspi_bootstrap_v25.py').read_bytes();asset=(self.source_root/'native_desktop_factory/native_runtime_assets/Atspi-2.0.typelib').read_bytes()
  require(digest(code)==self.native_manifest['source_sha256s']['native_desktop_factory/native_atspi_bootstrap_v25.py'] and digest(asset)==bootstrap.TYPELIB_SHA,'Pinned bootstrap bundle changed')
  self.sandbox.files.write(REMOTE+'/native_atspi_bootstrap_v25.py',code);self.sandbox.files.write(REMOTE+'/Atspi-2.0.typelib',asset)
  for mode in ['check','apply','namespace']:
   command='python3 '+shlex.quote(REMOTE+'/native_atspi_bootstrap_v25.py')+' '+mode+(' --typelib '+shlex.quote(REMOTE+'/Atspi-2.0.typelib') if mode!='namespace' else '')
   result=self._command('native-bootstrap-'+mode,command,timeout=20,request_timeout=30)
   require(not result.stderr,'Native bootstrap emitted unexplained stderr');value=json.loads(result.stdout)
   if mode=='namespace':require(value.get('namespace_available') is True and value.get('native_tree_qualified') is False,'Actual namespace prerequisite missing')
  self.bootstrap_receipt=bytes(self.sandbox.files.read(bootstrap.PREFIX+'/result.private.json',format='bytes'))
  installed=bytes(self.sandbox.files.read(bootstrap.PREFIX+'/Atspi-2.0.typelib',format='bytes'));require(installed==asset,'Actual installed supplemental bytes differ')
  prefix=self.out/'native-supplemental-content.private';prefix.mkdir(mode=0o700)
  exclusive(prefix/'result.private.json',self.bootstrap_receipt);exclusive(prefix/'Atspi-2.0.typelib',installed)
  json_put(self.root,self.out/'native-source-manifest.private.json',self.native_manifest);self.bootstrap_completed=True
 def prepare(self,**kwargs):
  self._bootstrap()
  # The existing original-source/profile/native-save path is unchanged. Its
  # virtual native_probe dispatch below uses the new child reader and GI env.
  super().prepare(**kwargs)
  raw=json.loads((self.out/'guest-probe-command-v16.private.json').read_bytes());base=json.loads(raw['stdout'])
  epoch=supplemental.supplemental_attestation(prefix=self.out/'native-supplemental-content.private',base_content_tree_sha256=base['content_tree_sha256'],source_manifest_sha256=self.native_manifest_sha256)
  json_put(self.root,self.out/'native-supplemental-epoch.private.json',epoch)
  self.receipt.update(native_source_manifest_sha256=self.native_manifest_sha256,supplemental_content_epoch_sha256=epoch['supplemental_content_epoch_sha256'],native_reader_sha256=digest(PROBE_SOURCE.read_bytes()),native_common_actor_paths=list(ACTOR_PATHS));self.persist()
 def native_probe(self,phase):
  require(self.bootstrap_completed,'Common native probe requires bootstrap before original prepare')
  points=list(self.requested_points or ([self.last_native_point] if self.last_native_point is not None else []))
  command='GI_TYPELIB_PATH='+shlex.quote(bootstrap.PREFIX)+' python3 '+shlex.quote(PROBE_PATH)+' --filename '+shlex.quote(self.filename)+' --width 1280 --height 800 --points-json '+shlex.quote(json.dumps(points,separators=(',',':')))
  result=self.sandbox.commands.run(command,timeout=45,request_timeout=55)
  json_put(self.root,self.out/f'native-probe-{self.native_sequence:03d}.private.json',{'schema':'cua-native-guest-probe-command-v31','phase':phase,'exit_code':result.exit_code,'stdout':result.stdout,'stderr':result.stderr,'command_sha256':digest(command.encode()),'native_source_manifest_sha256':self.native_manifest_sha256});self.native_sequence+=1
  require(result.exit_code==0 and len(result.stdout.encode())<=262144,'Common native probe failed or exceeded bound')
  value=json.loads(result.stdout)
  if value.get('status')!='observed' and 'private_error_file' in value:
   error_raw=bytes(self.sandbox.files.read(str(reader.PRIVATE_ERROR_PATH),format='bytes'));ref=value['private_error_file']
   require(digest(error_raw)==ref['sha256'] and len(error_raw)==ref['bytes'] and ref['mode']==0o600,'Native private error readback differs')
   json_put(self.root,self.out/f'native-error-{self.native_sequence-1:03d}.private.json',json.loads(error_raw))
  # Deprecation/runtime warnings are retained, but success still requires the
  # actual typed native output. Unknown stderr is not silently accepted.
  require(not result.stderr,'Common native probe emitted unexplained stderr')
  require(value.get('schema')==PROBE_SCHEMA and value.get('status')=='observed' and value.get('probe_source_sha256')==digest(PROBE_SOURCE.read_bytes()) and
   value.get('native_mutations')==0 and value.get('raster_equality_used') is False and value.get('recursive_collection_query_called') is False and value.get('focus_from_selection') is False,'Actual bounded native metadata unavailable')
  if value.get('focus_editable'):
   require(value.get('actual_native_focus_proof') is True and any(t['ref']==value['focus_id'] and t['keyboard'] for t in value['targets']),'Actual native focused object proof missing')
  return value
 def dispatch_model(self,raw,observation,*,actor_deadline):
  action=normalize_model_action(raw,observation,current_frame_id=observation.frame_id)
  points=[list(action[k].values()) for k in ['target','from','to'] if k in action and set(action[k])=={'x','y'}]
  require(len(points)<=2,'Native point action bound changed');self.requested_points=[[action[k]['x'],action[k]['y']] for k in ['target','from','to'] if k in action and set(action[k])=={'x','y'}]
  try:
   result=super().dispatch_model(raw,observation,actor_deadline=actor_deadline)
   if result[1]['native_status']=='applied' and self.requested_points:self.last_native_point=self.requested_points[-1]
   return result
  finally:self.requested_points=[]

class CommonGuestFactory:
 def __init__(self,*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
  self.source_root=Path(source_root or Path(__file__).resolve().parents[1]);self.manifest=checked_runtime_manifest(manifest,self.source_root);self.qualification=qualification;self.auditor=independent_raw_auditor
 def require_activation(self):
  checked_runtime_manifest(self.manifest,self.source_root);row=self.qualification
  require(type(row) is dict and row.get('schema')=='cua-native-common-guest-qualification-v31' and row.get('source_manifest_sha256')==digest(canonical(self.manifest)) and row.get('actor_paths')==list(ACTOR_PATHS) and row.get('native_policy_sha256')==POLICY_SHA and row.get('old_results_reclassified') is False,'Fresh common native qualification required before provider calls')
  require(callable(self.auditor),'Independent common native raw reopening required')
  proof=self.auditor(row)
  require(type(proof) is dict and proof.get('raw_native_evidence_reopened') is True and proof.get('completed_current_control_trios')==120 and proof.get('all_seven_actor_paths_verified') is True and
   proof.get('app_kinds')==['calc','impress','writer'] and proof.get('base_and_supplemental_content_reopened') is True and proof.get('actor_clock_and_distinct_reset_verified') is True,'Actual common native qualification incomplete')
  return row
 def wrap_owned_guest(self,sandbox,*,root,out,filename,lease_started_monotonic):
  require(re.fullmatch(r'[A-Za-z0-9_.-]{1,160}\.(xlsx|pptx|docx)',filename) is not None,'Owned native filename invalid')
  require(Path(out).parent.parent==Path(root) and Path(out).is_dir(),'Owned native guest storage hierarchy required')
  return CommonNativeModelGuest(sandbox,root=Path(root),out=Path(out),filename=filename,lease_started_monotonic=lease_started_monotonic,native_manifest=self.manifest,source_root=self.source_root)
 def create_guest(self,*,root,out,filename):
  self.require_activation()
  require(re.fullmatch(r'[A-Za-z0-9_.-]{1,160}\.(xlsx|pptx|docx)',filename) is not None,'Owned native filename invalid before create')
  from .reconcile_interrupted_sweep import active_hashes
  from .bounded_guest_transport_v17 import BoundedSandbox
  from e2b_desktop import Sandbox
  active,count=active_hashes();require(not active and count==0,'Common native create requires active-zero')
  out=Path(out);require(out.parent.parent==Path(root) and out.is_dir(),'Owned native create storage hierarchy required')
  started=time.monotonic();exclusive(out/'native-create-intent-v31.private.json',canonical({'maximum_creates':1,'lease_seconds':1200,'source_manifest_sha256':digest(canonical(self.manifest)),'automatic_restarts':0}))
  raw=Sandbox.create(template='desktop',resolution=(1280,800),timeout=1200,allow_internet_access=False,metadata={'envloop_purpose':'uniform-native-common-v31'})
  # Raw handle is journaled before any wrapper or source/profile preparation.
  self.last_raw_guest=raw;self.last_raw_guest_handle=raw.sandbox_id
  try:
   exclusive(out/'native-raw-created-v31.private.json',canonical({'sandbox_id':raw.sandbox_id,'sandbox_id_sha256':digest(raw.sandbox_id.encode())}))
   return self.wrap_owned_guest(BoundedSandbox(raw),root=root,out=out,filename=filename,lease_started_monotonic=started)
  except BaseException:
   # One cleanup invocation, with unknown outcomes retained rather than retried.
   cleanup={'sandbox_id_sha256':digest(raw.sandbox_id.encode()),'kill_acknowledged':None,'sandbox_running_after_kill':None,'automatic_retries':0}
   try:cleanup.update(kill_acknowledged=bool(raw.kill()),sandbox_running_after_kill=bool(raw.is_running(request_timeout=12)))
   except BaseException as error:cleanup['error_class']=type(error).__name__
   exclusive(out/'native-constructor-cleanup-v31.private.json',canonical(cleanup));raise

@contextmanager
def runtime_context(factory):
 require(isinstance(factory,CommonGuestFactory) and _CURRENT.get() is None,'Exclusive common native runtime context required');factory.require_activation();token=_CURRENT.set(factory)
 try:yield factory
 finally:_CURRENT.reset(token)

def create_guest(*,root,out,filename):
 factory=_CURRENT.get();require(factory is not None,'Common native runtime source context missing before provider create')
 return factory.create_guest(root=root,out=out,filename=filename)

def prepare_host_bundle(*,output,source_root=None):
 source_root=Path(source_root or Path(__file__).resolve().parents[1]);manifest=source_manifest(source_root);output=Path(output);output.mkdir(mode=0o700,exist_ok=False)
 for name in (*PEERS,'native_atspi_bootstrap_v25.py'):
  raw=(source_root/'native_desktop_factory'/name).read_bytes();exclusive(output/name,raw)
 exclusive(output/'Atspi-2.0.typelib',(source_root/'native_desktop_factory/native_runtime_assets/Atspi-2.0.typelib').read_bytes())
 exclusive(output/'source-manifest.private.json',canonical(manifest))
 return {'schema':'cua-native-common-host-bundle-v31','source_manifest_sha256':digest(canonical(manifest)),'provider_calls':0,'native_qualification_passed':False}

def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['source','prepare-host']);parser.add_argument('--out',type=Path);args=parser.parse_args()
 print(json.dumps(source_manifest() if args.mode=='source' else prepare_host_bundle(output=args.out),sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
