import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from native_desktop_factory import current_episode_paid_id_v22 as current
from native_desktop_factory import prospective_model_worker_v21 as historical

class HookTests(unittest.TestCase):
 def test_new_namespace_preserves_old_engine_and_only_changes_deadline_id_hook(self):
  self.assertIsNot(current.DesktopProspectiveModelWorker,historical.DesktopProspectiveModelWorker)
  self.assertIn('actual_sample_attempt_id',current.DesktopProspectiveModelWorker._episode.__code__.co_names)
  self.assertNotIn('actual_sample_attempt_id',historical.DesktopProspectiveModelWorker._episode.__code__.co_names)
  self.assertEqual((current.transport.MAX_ACTIONS,current.transport.ACTOR_WALL_SECONDS,current.transport.LEASE_SECONDS),(90,720,1200))
 def test_actual_shared_base_envelope_is_checked_against_worker_request(self):
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);root.chmod(0o700);native=root/'native';native.mkdir(mode=0o700);session_root=root/'session';(session_root/'paid').mkdir(parents=True,mode=0o700)
   identifier='base-selection-desktop-native-sample-000-003';request={'step':3,'task_id':'train-fixture','package_sha256':'a'*64,'checkpoint_path_sha256':'b'*64,'frame_sha256':'c'*64}
   request_ref=current.write(native/'raw.private.json',request);copied=current.write(session_root/'paid'/'worker.private.json',request)
   envelope={'schema':'cua-full-study-shared-base-paid-request-v1','category':'tinker','cell_id':'desktop-native','selection_attempt':'base-selection-desktop-native','action_profile':'scale-action-profile-v0.6.6',
    **{k:request[k] for k in ['task_id','package_sha256','checkpoint_path_sha256','frame_sha256']},'worker_request_ref':{'path':'paid/worker.private.json','sha256':copied['sha256']}}
   env_ref=current.write(session_root/'paid'/(identifier+'.request.private.json'),envelope)
   session=SimpleNamespace(owner='desktop-native:shared-base',directory=session_root,attempt_id='base-selection-desktop-native',_audit_paid_files=lambda:None,_events=lambda kind:[],
    budget=SimpleNamespace(owner_attempts=lambda owner:{identifier:{'category':'tinker','status':'uncertain','request_sha256':env_ref['sha256'],'work_sha256':env_ref['sha256']}}),study=None)
   paid=current.PaidCalls(attempt_id=session.attempt_id,checkpoint='b'*64,identities=[],output_dir=native,runtime='d'*64,quote='1',session=session)
   paid.last_attempt_id=identifier;worker=current.write(native/'paid'/(identifier+'.request.private.json'),request)
   intent=current.write(native/'paid'/(identifier+'.intent.private.json'),{'attempt_id':identifier,'category':'tinker','request_sha256':worker['sha256']})
   current.write(native/'paid'/(identifier+'.dispatched.private.json'),{'intent_sha256':intent['sha256']})
   self.assertEqual(paid.actual_sample_attempt_id(ordinal=0,step=3),identifier)
   (session_root/'paid'/'worker.private.json').write_bytes(b'{}')
   with self.assertRaises(ValueError):paid.actual_sample_attempt_id(ordinal=0,step=3)
 def test_actual_durable_intent_and_dispatch_required_before_returning_id(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);root.chmod(0o700);paid=current.PaidCalls(attempt_id='real-final',checkpoint='a'*64,identities=[],output_dir=root,runtime='b'*64,quote='1',study=None)
   identifier='real-final-sample-000-003';paid.last_attempt_id=identifier
   with self.assertRaises((OSError,ValueError)):paid.actual_sample_attempt_id(ordinal=0,step=3)
   request={'step':3};request_ref=current.write(root/'paid'/(identifier+'.request.private.json'),request)
   intent=current.write(root/'paid'/(identifier+'.intent.private.json'),{'attempt_id':identifier,'category':'tinker','request_sha256':request_ref['sha256']})
   current.write(root/'paid'/(identifier+'.dispatched.private.json'),{'intent_sha256':intent['sha256']})
   self.assertEqual(paid.actual_sample_attempt_id(ordinal=0,step=3),identifier)
   with self.assertRaises(ValueError):paid.actual_sample_attempt_id(ordinal=0,step=4)
   (root/'paid'/(identifier+'.request.private.json')).write_bytes(b'{}')
   with self.assertRaises(ValueError):paid.actual_sample_attempt_id(ordinal=0,step=3)

if __name__=='__main__':unittest.main()
