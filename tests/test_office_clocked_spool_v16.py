import tempfile,time,unittest
from pathlib import Path
from tools import office_owned_folder_runtime_v2 as old
from tools.office_clocked_typed_spool_v16 import NativeOperationSpool
from tools.office_current_native_clock_v4 import Actor
from cursibench import native_surface_guard_policy_v1 as policy
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached

class ClockedSpoolTests(unittest.TestCase):
 def constructed(self):
  root=Path(tempfile.mkdtemp()).resolve();root.chmod(0o700)
  account=old.AccountLease('a'*64,expires_at_ms=int(time.time()*1000)+60000,root=root);account.acquire()
  host=object.__new__(NativeOperationSpool);host.admission={'account_principal_sha256':'a'*64,'folder_scope_sha256':'b'*64};host.sequence=0;calls=[]
  def request(op,payload):
   calls.append(op);self.assertEqual(op,'actor_open');return {'native_policy_sha256':policy.POLICY_SHA,'owned_document_editing':True,'window_sha256':'c'*64}
  host.request=request
  actor=host.actor_open({}, {'cell_id':'powerpoint-web'}, root/'actual-actor.private',account_lease=account)
  return host,actor,calls
 def test_real_base_actor_open_clock_and_typed_lease(self):
  host,actor,calls=self.constructed();self.assertIsInstance(actor,Actor);self.assertIs(host.actor,actor)
  started=time.monotonic();actor.bind_actor_clock(started,started+720)
  self.assertEqual(actor.deadline,started+720);self.assertGreater(host.actor_deadline_epoch_ms,int(time.time()*1000));checked=host.check_native_lease(policy.validate_lease(actor.lease));policy.verify_artifact(actor.root,checked['evidence']);self.assertEqual(calls,['actor_open'])
  with self.assertRaises(ValueError):actor.bind_actor_clock(started,started+720)
 def test_actual_clock_observe_preserves_typed_deadline_before_native_read(self):
  host,actor,calls=self.constructed();started=time.monotonic()-721;actor.bind_actor_clock(started,started+720)
  with self.assertRaises(ActorDeadlineReached):actor.observe(memory='')
  self.assertEqual(calls,['actor_open'])
if __name__=='__main__':unittest.main()
