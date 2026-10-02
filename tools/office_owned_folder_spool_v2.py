"""One-use native Office host operation spool, separate from model sampling.

A CUA host must execute the reviewed UI operation and publish actual raw
receipts. This transport cannot manufacture an upload, download or cleanup.
"""
from __future__ import annotations
import json,os,time
from pathlib import Path
from tools.office_owned_folder_runtime_v2 import require,private,canonical,write_new,sha,OfficeRuntimeError

OPERATIONS={'folder_inventory','create_document','double_download','close_document','remove_document','actor_open','native_surface','resolve_native_targets','dispatch_native_primitive'}

class NativeOperationSpool:
 def __init__(self,root,*,source_admission,clock=time.monotonic,poll_seconds=0.25,deadline_seconds=180):
  self.root=Path(root);self.root.mkdir(mode=0o700,exist_ok=False);self.clock=clock;self.poll_seconds=poll_seconds;self.deadline_seconds=deadline_seconds;self.sequence=0
  self.admission=json.loads(private(source_admission));require(self.admission.get('schema')=='office-owned-folder-native-host-source-review-v2' and
   self.admission.get('approved') is True and self.admission.get('single_account') is True and self.admission.get('graph_used') is False,
   'Exact native host source review required')
 def capabilities(self):return {'surface':'original-office-web','same_account':True,'graph':False,'native_operations_source_reviewed':self.admission.get('approved') is True,'qualified_native_operations':self.admission.get('actual_native_lifecycle_qualified') is True}
 def request(self,operation,payload):
  require(operation in OPERATIONS,'Unsupported native Office operation');ordinal=self.sequence;self.sequence+=1
  directory=self.root/f'operation-{ordinal:04d}';directory.mkdir(mode=0o700)
  body={'schema':'office-owned-folder-operation-request-v2','operation':operation,'sequence':ordinal,'payload':payload,
   'account_principal_sha256':self.admission['account_principal_sha256'],'folder_scope_sha256':self.admission['folder_scope_sha256'],
   'source_review_sha256':sha(canonical(self.admission)),'one_use':True}
  write_new(directory/'request.private.json',canonical(body));deadline=self.clock()+self.deadline_seconds
  response=directory/'response.private.json'
  while not response.exists():
   if self.clock()>=deadline:
    write_new(directory/'terminal-uncertain.private.json',canonical({'status':'native_host_response_missing_no_retry','sequence':ordinal}));raise OfficeRuntimeError('Native host response missing; operation may be uncertain')
   time.sleep(self.poll_seconds)
  value=json.loads(private(response));require(value.get('schema')=='office-owned-folder-operation-response-v2' and value.get('request_sha256')==sha(canonical(body)) and
   value.get('sequence')==ordinal and value.get('operation')==operation,'Native host response changed operation')
  write_new(directory/'consumed.private.json',canonical({'response_sha256':sha(private(response)),'one_use':True}))
  require(value.get('status')=='completed','Native host operation failed without automatic retry')
  return value['result']
 def owned_folder_inventory(self):return self.request('folder_inventory',{})
 def create_from_baseline(self,actor_task,baseline,*,purpose):
  return self.request('create_document',{'actor_task':actor_task,'baseline_path':str(baseline),'baseline_sha256':sha(private(baseline)),'purpose':purpose})
 def double_download(self,item,*,purpose):return self.request('double_download',{'item':item,'purpose':purpose})
 def close_document(self,item):return self.request('close_document',{'item':item})
 def remove_owned_item(self,item):return self.request('remove_document',{'item':item})
 def actor_open(self,item,actor_task,artifact_root,*,account_lease):
  from tools.office_owned_folder_native_guard_v2 import OwnedNativeActor
  from cursibench import native_surface_guard_policy_v1 as policy
  result=self.request('actor_open',{'item':item,'actor_task':actor_task,'artifact_root':str(artifact_root)})
  require(result.get('native_policy_sha256')==policy.POLICY_SHA and result.get('owned_document_editing') is True,'Native actor ownership/policy not observed')
  self.account_lease=account_lease;self.actor_root=Path(artifact_root)
  raw=private(account_lease.path);tick=time.monotonic()
  lease={'schema':'native-surface-lease-v1','lease_id':account_lease.token,'cell_id':actor_task['cell_id'],'account_sha256':self.admission['account_principal_sha256'],
   'workspace_sha256':self.admission['folder_scope_sha256'],'window_sha256':result['window_sha256'],'owner_sha256':sha(raw),'issued_at':tick,
   'expires_at':tick+max(0,(account_lease.expires_at_ms-int(time.time()*1000))/1000),
   'evidence':{'schema':'native-guard-artifact-ref-v1','path':'account-lease.private.json','sha256':sha(raw),'size':len(raw),'kind':'lease_evidence'}}
  actor=OwnedNativeActor(self,actor_task=actor_task,item=item,lease=lease,artifact_root=artifact_root)
  write_new(actor.root/'account-lease.private.json',raw);return actor
 def current_native_surface(self,item,*,phase):
  result=self.request('native_surface',{'item':item,'phase':phase});root=Path(self.admission['native_evidence_root']).resolve();ref=result['cropped_image_ref']
  require(not Path(ref['path']).is_absolute() and '..' not in Path(ref['path']).parts,'Native frame escaped evidence root');path=root/ref['path']
  require(path.resolve().is_relative_to(root),'Native frame escaped evidence root');raw=private(path);require(sha(raw)==ref['sha256'],'Native frame bytes changed')
  return {'cropped_image_bytes':raw,'native_metadata':result['native_metadata']}
 def check_native_lease(self,lease):
  from cursibench import native_surface_guard_policy_v1 as policy
  require(self.account_lease.token==lease['lease_id'] and self.account_lease.active(),'Native shared account lease lost')
  raw=private(self.account_lease.path);name='lease-check-'+str(self.sequence)+'.private.json';write_new(self.actor_root/name,raw);tick=time.monotonic()
  return {'schema':'native-surface-lease-check-v1','lease_sha256':policy.digest(lease),'status':'active','checked_at':tick,'expires_at':min(lease['expires_at'],tick+10),
   'evidence':{'schema':'native-guard-artifact-ref-v1','path':name,'sha256':sha(raw),'size':len(raw),'kind':'lease_check'}}
 def resolve_current_action_targets(self,item,action,current):return self.request('resolve_native_targets',{'item':item,'action':action,'current':current})
 def dispatch_native_primitive(self,item,action,resolved):return self.request('dispatch_native_primitive',{'item':item,'action':action,'resolved':resolved})
