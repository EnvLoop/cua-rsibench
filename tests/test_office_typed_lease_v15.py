import json,tempfile,time,unittest
from pathlib import Path
from tools import office_owned_folder_runtime_v2 as old
from tools.office_owned_folder_spool_v2 import NativeOperationSpool as Original
from tools.office_owned_folder_spool_v3 import NativeOperationSpool
from cursibench import native_surface_guard_policy_v1 as policy

class TypedLeaseTests(unittest.TestCase):
 def fixture(self):
  root=Path(tempfile.mkdtemp()).resolve();root.chmod(0o700);actor=root/'actor';actor.mkdir(mode=0o700)
  account=old.AccountLease('a'*64,expires_at_ms=int(time.time()*1000)+60000,root=root);account.acquire();raw=old.private(account.path);old.write_new(actor/'account-lease.private.json',raw);now=time.monotonic()
  row={'schema':'native-surface-lease-v1','lease_id':account.token,'cell_id':'powerpoint-web','account_sha256':'a'*64,'workspace_sha256':'b'*64,'window_sha256':'c'*64,'owner_sha256':old.sha(raw),'issued_at':now-1,'expires_at':now+50,'evidence':{'schema':'native-guard-artifact-ref-v1','path':'account-lease.private.json','sha256':old.sha(raw),'size':len(raw),'kind':'lease_evidence'}}
  host=object.__new__(NativeOperationSpool);host.account_lease=account;host.actor_root=actor;host.sequence=1;host.bound_native_lease=policy.validate_lease(row)
  return host,row
 def test_actual_dict_and_dataclass_check_and_durable_evidence(self):
  host,row=self.fixture()
  for lease in (row,policy.validate_lease(row)):
   value=host.check_native_lease(lease);policy.validate_lease_check(value,policy.validate_lease(row));policy.verify_artifact(host.actor_root,value['evidence']);self.assertEqual(value['status'],'active')
  self.assertEqual(len(list(host.actor_root.glob('lease-check-*'))),2)
 def test_old_callback_fails_before_evidence_on_actual_policy_dataclass(self):
  host,row=self.fixture()
  with self.assertRaises(TypeError):Original.check_native_lease(host,policy.validate_lease(row))
  self.assertFalse(list(host.actor_root.glob('lease-check-*')))
 def test_actual_inactive_token_and_owner_bytes_rejected(self):
  for mutation in ('expired','token','owner'):
   host,row=self.fixture();value=json.loads(old.private(host.account_lease.path))
   if mutation=='expired':value['expires_at_ms']=int(time.time()*1000)-1
   if mutation=='token':value['token']='different'
   raw=old.canonical(value)+(b' ' if mutation=='owner' else b'');host.account_lease.path.write_bytes(raw)
   with self.assertRaises(ValueError):host.check_native_lease(policy.validate_lease(row))
 def test_copied_evidence_and_bound_lease_tamper_rejected(self):
  host,row=self.fixture();(host.actor_root/'account-lease.private.json').write_bytes(b'drift')
  with self.assertRaises(ValueError):host.check_native_lease(policy.validate_lease(row))
  host,row=self.fixture();row['window_sha256']='d'*64
  with self.assertRaises(ValueError):host.check_native_lease(policy.validate_lease(row))
if __name__=='__main__':unittest.main()
