"""Typed shared-policy lease check with actual durable account ownership."""
import json,time
from tools.office_owned_folder_spool_v2 import NativeOperationSpool as OriginalSpool
from tools.office_owned_folder_runtime_v2 import require,private,write_new,sha
from cursibench import native_surface_guard_policy_v1 as policy

class NativeOperationSpool(OriginalSpool):
 def actor_open(self,*args,**kwargs):
  actor=super().actor_open(*args,**kwargs);self.bound_native_lease=policy.validate_lease(actor.lease);return actor
 def check_native_lease(self,lease):
  checked=policy.validate_lease(lease)
  require(policy.digest(checked)==policy.digest(self.bound_native_lease),'Native lease binding changed')
  require(self.account_lease.token==checked.lease_id and self.account_lease.active(),'Native shared account lease lost')
  raw=private(self.account_lease.path);record=json.loads(raw)
  require(record.get('token')==checked.lease_id and record.get('expires_at_ms')==self.account_lease.expires_at_ms and
   type(record.get('expires_at_ms')) is int and int(time.time()*1000)<record['expires_at_ms'] and
   sha(raw)==checked.owner_sha256==checked.evidence.sha256 and len(raw)==checked.evidence.size,
   'Native durable lease owner or deadline changed')
  policy.verify_artifact(self.actor_root,checked.evidence)
  tick=time.monotonic();expires=min(checked.expires_at,tick+10,tick+(record['expires_at_ms']-time.time()*1000)/1000)
  require(checked.issued_at<=tick<expires,'Native shared account lease expired')
  number=getattr(self,'lease_check_sequence',0);self.lease_check_sequence=number+1
  name='lease-check-'+str(number)+'.private.json';write_new(self.actor_root/name,raw)
  require(private(self.account_lease.path)==raw and self.account_lease.active(),'Native lease changed during durable check')
  value={'schema':'native-surface-lease-check-v1','lease_sha256':policy.digest(checked),'status':'active','checked_at':tick,'expires_at':expires,
   'evidence':{'schema':'native-guard-artifact-ref-v1','path':name,'sha256':sha(raw),'size':len(raw),'kind':'lease_check'}}
  policy.validate_lease_check(value,checked);policy.verify_artifact(self.actor_root,value['evidence']);return value
