"""Real guard call-path checks, with offline native metadata and images only."""
import io
from pathlib import Path
import tempfile
import time
import unittest
from PIL import Image
from cursibench import native_surface_guard_policy_v1 as policy
from tools.office_owned_folder_native_guard_v2 import OwnedNativeActor


def png(color):
 out=io.BytesIO();Image.new('RGB',(1000,700),color).save(out,format='PNG');return out.getvalue()

class Host:
 def __init__(self):self.calls=[];self.missing=False;self.unsafe=False;self.fail=False;self.count=0
 def current_native_surface(self,item,*,phase):
  self.calls.append(phase);self.count+=1
  return {'cropped_image_bytes':png('white' if self.count==1 else 'blue'),'native_metadata':{
   'account_principal_sha256':'a'*64,'folder_scope_sha256':'b'*64,'document_identity_sha256':'f'*64,'window_sha256':'c'*64,
   'owned_document_editing':True,'private_header_excluded':True,'viewport':[1000,700],'native_context_id':'native-editor','modal_id':'none','focus_id':'edit',
   'targets':[{'ref':'edit','bounds':[20,30,200,40],'visible':True,'enabled':not self.unsafe,'obscured':False,'keyboard':True,'actions':['click','double_click','type','key','scroll']}]}}
 def check_native_lease(self,lease):
  tick=time.monotonic();return {'schema':'native-surface-lease-check-v1','lease_sha256':policy.digest(lease),'status':'active','checked_at':tick,'expires_at':tick+10,
   'evidence':{'schema':'native-guard-artifact-ref-v1','path':'actual-lease.private','sha256':'e'*64,'size':1,'kind':'lease_check'}}
 def resolve_current_action_targets(self,item,action,current):self.calls.append('resolve');return {'status':'missing' if self.missing else 'current'}
 def dispatch_native_primitive(self,item,action,resolved):
  self.calls.append('driver')
  if self.fail:raise RuntimeError('uncertain fixture driver')
  return {'status':'applied','focus_verified_before_keyboard':True}

class GuardTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();tick=time.monotonic();self.host=Host()
  lease={'schema':'native-surface-lease-v1','lease_id':'owned-lease','cell_id':'powerpoint-web','account_sha256':'a'*64,'workspace_sha256':'b'*64,'window_sha256':'c'*64,'owner_sha256':'d'*64,'issued_at':tick-1,'expires_at':tick+600,
   'evidence':{'schema':'native-guard-artifact-ref-v1','path':'lease.private','sha256':'e'*64,'size':1,'kind':'lease_evidence'}}
  self.actor=OwnedNativeActor(self.host,actor_task={'task_id':'ppt-wdi-generic','package_sha256':'e'*64,'visible_instruction':'Reconcile the displayed fields.','cell_id':'powerpoint-web'},item={'item_identity_sha256':'f'*64},lease=lease,artifact_root=Path(self.temp.name)/'actor')
 def tearDown(self):self.temp.cleanup()
 def action(self,obs):return {'version':'scale-computer-use-v0.6','task_id':obs.task_id,'task_binding_sha256':obs.task_binding_sha256,'frame_id':obs.frame_id,'step':obs.step,'type':'click','target':{'x':40,'y':40},'memory':''}
 def test_different_pixels_and_actual_safe_geometry_dispatch_once(self):
  obs=self.actor.observe();result=self.actor.dispatch(self.action(obs));self.assertEqual(result['status'],'applied');self.assertEqual(self.host.calls,['observation','predispatch','resolve','driver'])
 def test_removed_accepted_target_consumes_nonce_without_driver(self):
  obs=self.actor.observe();self.host.missing=True;self.assertEqual(self.actor.dispatch(self.action(obs))['status'],'rejected');self.assertNotIn('driver',self.host.calls)
  self.assertTrue((self.actor.root/'turn-000/nonce.private.json').exists());self.assertFalse((self.actor.root/'turn-000/intent.private.json').exists())
 def test_current_disabled_target_rejected_before_resolution(self):
  obs=self.actor.observe();self.host.unsafe=True;self.assertEqual(self.actor.dispatch(self.action(obs))['status'],'rejected');self.assertNotIn('resolve',self.host.calls)
 def test_invalid_model_output_consumes_turn_without_native_driver(self):
  self.actor.observe();result=self.actor.reject_model_output('not a JSON action');self.assertEqual(result['status'],'rejected');self.assertNotIn('driver',self.host.calls);self.assertEqual(self.actor.step,1)
  self.assertTrue((self.actor.root/'turn-000/nonce.private.json').exists());self.actor.observe()
 def test_driver_uncertainty_quarantines_without_replay(self):
  obs=self.actor.observe();self.host.fail=True
  with self.assertRaises(policy.GuardError):self.actor.dispatch(self.action(obs))
  self.assertEqual(self.host.calls.count('driver'),1)
  with self.assertRaises(ValueError):self.actor.observe()

if __name__=='__main__':unittest.main()
