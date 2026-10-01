"""Raw safety evidence and one-use boundary tests with no browser/provider."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from gitlab_world import v066_native_surface_adapter_v9 as adapter
from cursibench import native_surface_guard_policy_v1 as policy

class StoreTests(unittest.TestCase):
 def test_exclusive_evidence_is_owner_only_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);store=adapter.EvidenceStore(root);ref=store.json('turn-000/intent.private.json',{'action':'click'},'action_intent')
   self.assertEqual((root/ref['path']).stat().st_mode&0o077,0)
   self.assertEqual(policy.validate_artifact_ref(ref).kind,'action_intent')
   with self.assertRaises(policy.GuardError):store.json('turn-000/intent.private.json',{'different':True},'action_intent')
 def test_kernel_lease_is_real_and_release_invalidates_fresh_check(self):
  with tempfile.TemporaryDirectory() as folder:
   active=SimpleNamespace(page=object(),project_path='/group/project',step=0)
   guard=adapter.NativeGuard(active,Path(folder),account_uid='17',partition='train');guard.bind()
   first=guard.lease_check(policy.validate_lease(guard.lease));self.assertEqual(first['status'],'active')
   guard.close();active.step=1;second=guard.lease_check(policy.validate_lease(guard.lease));self.assertEqual(second['status'],'inactive')
 def test_ownership_requires_current_native_account_and_project_origin(self):
  with tempfile.TemporaryDirectory() as folder:
   active=SimpleNamespace(page=object(),project_path='/group/project',step=0,_scoped_url=lambda:True)
   guard=adapter.NativeGuard(active,Path(folder),account_uid='17',partition='selection')
   meta={'url':'http://127.0.0.1:8018/group/project/issues','top':True,'visible':True,'account_uid':'17'}
   self.assertTrue(guard.owned(meta));self.assertFalse(guard.owned(meta|{'account_uid':'18'}));self.assertFalse(guard.owned(meta|{'url':'https://example.com/group/project'}))
 def test_native_metadata_has_no_task_answer_or_field_value_logic(self):
  self.assertNotIn('expected_priority',adapter.META_JS);self.assertNotIn('oracle',adapter.META_JS);self.assertNotIn('.value',adapter.META_JS)
  self.assertIn('document_id',adapter.META_JS);self.assertIn('elementFromPoint',adapter.META_JS)

if __name__=='__main__':unittest.main()

import asyncio,io,copy
from PIL import Image
from unittest.mock import AsyncMock,patch
from cursibench.scale_action_output_v066 import normalize_model_action

def png(color):
 buf=io.BytesIO();Image.new('RGB',(16,16),color).save(buf,format='PNG');return buf.getvalue()

class FakePage:
 def __init__(self):self.url='http://127.0.0.1:8018/group/project/issues/1';self.phase=0;self.unsafe=False;self.missing=False;self.connected=True;self.lookup_calls=0
 def locator(self,*args):return self
 async def element_handle(self):return object()
 async def element_handles(self):
  self.lookup_calls+=1
  if self.missing:return []
  return [SimpleNamespace(evaluate=AsyncMock(return_value={"connected":self.connected,"ref":"g1","document_id":"owned-doc"}))]
 async def screenshot(self,**kwargs):self.phase+=1;return png('white' if self.phase==1 else 'black')
 async def evaluate(self,script,args):
  row={'ref':'g1','bounds':[1,1,8,8],'visible':True,'enabled':not self.unsafe,'obscured':False,'keyboard':True,
   'actions':['click','double_click','type','key','scroll','drag'],'role':'textbox','label':'Edit'}
  return {'schema':'gitlab-native-surface-v9','top':True,'visible':True,'account_uid':'17','document_id':'owned-doc','path':'/group/project/issues/1',
   'viewport':[16,16],'targets':[row],'focus':row,'modals':[],'hits':[]}

class DispatchTests(unittest.IsolatedAsyncioTestCase):
 async def test_observation_never_resolves_unrelated_handles(self):
  with tempfile.TemporaryDirectory() as folder:
   page=FakePage();page.missing=True
   active=SimpleNamespace(page=page,project_path='/group/project',step=0,task={'task_id':'train-1','package_sha256':'a'*64,'visible_instruction':'Edit owned label'},_scoped_url=lambda:True,latest=None,finished=False)
   guard=adapter.NativeGuard(active,Path(folder),account_uid='17',partition='train');guard.bind()
   frame=await guard.observe('');self.assertEqual(page.lookup_calls,0);self.assertEqual(frame.handles,{})
   guard.close()
 async def test_missing_or_disconnected_requested_ref_rejected_before_intent(self):
  for missing in [True,False]:
   with self.subTest(missing=missing),tempfile.TemporaryDirectory() as folder:
    page=FakePage();active=SimpleNamespace(page=page,project_path='/group/project',step=0,task={'task_id':'train-1','package_sha256':'a'*64,'visible_instruction':'Edit owned label'},_scoped_url=lambda:True,latest=None,finished=False)
    guard=adapter.NativeGuard(active,Path(folder),account_uid='17',partition='train');guard.bind();frame=await guard.observe('')
    page.missing=missing;page.connected=False
    action=normalize_model_action('{"type":"click","target":{"ref":"g1"},"memory":""}',frame.observation,current_frame_id=frame.observation.frame_id)
    with patch.object(guard,'drive',new=AsyncMock()) as driver:
     result=await guard.dispatch(action);driver.assert_not_awaited()
    self.assertEqual(result['status'],'rejected');self.assertEqual(active.step,1)
    receipt=json.loads((Path(folder)/'turn-000/receipt.private.json').read_bytes())
    self.assertEqual(receipt['driver_result'],'not_attempted');self.assertIsNone(receipt['intent'])
    self.assertFalse((Path(folder)/'turn-000/intent.private.json').exists());guard.close()
 async def test_pixel_difference_accepts_owned_native_target_with_real_durable_intent(self):
  with tempfile.TemporaryDirectory() as folder:
   page=FakePage();active=SimpleNamespace(page=page,project_path='/group/project',step=0,task={'task_id':'train-1','package_sha256':'a'*64,'visible_instruction':'Edit owned label'},
    _scoped_url=lambda:True,latest=None,finished=False)
   guard=adapter.NativeGuard(active,Path(folder),account_uid='17',partition='train');guard.bind()
   frame=await guard.observe('');action=normalize_model_action('{"type":"click","target":{"ref":"g1"},"memory":""}',frame.observation,current_frame_id=frame.observation.frame_id)
   with patch.object(guard,'drive',new=AsyncMock()) as driver:result=await guard.dispatch(action);driver.assert_awaited_once_with(action)
   self.assertEqual(result,{'status':'applied','code':'ok'});self.assertEqual(active.step,1)
   receipt=json.loads((Path(folder)/'turn-000/receipt.private.json').read_bytes());self.assertEqual(receipt['driver_result'],'succeeded')
   self.assertTrue((Path(folder)/'turn-000/intent.private.json').exists());self.assertTrue((Path(folder)/'turn-000/nonce.private.json').exists())
   self.assertNotEqual((Path(folder)/'turn-000/observation.png').read_bytes(),(Path(folder)/'turn-000/predispatch.png').read_bytes());guard.close()
 async def test_disabled_predispatch_target_consumes_nonce_without_driver_or_intent(self):
  with tempfile.TemporaryDirectory() as folder:
   page=FakePage();active=SimpleNamespace(page=page,project_path='/group/project',step=0,task={'task_id':'train-1','package_sha256':'a'*64,'visible_instruction':'Edit owned label'},_scoped_url=lambda:True,latest=None,finished=False)
   guard=adapter.NativeGuard(active,Path(folder),account_uid='17',partition='train');guard.bind();frame=await guard.observe('');page.unsafe=True
   action=normalize_model_action('{"type":"click","target":{"ref":"g1"},"memory":""}',frame.observation,current_frame_id=frame.observation.frame_id)
   with patch.object(guard,'drive',new=AsyncMock()) as driver:result=await guard.dispatch(action);driver.assert_not_awaited()
   self.assertEqual(result['status'],'rejected');self.assertEqual(active.step,1);self.assertFalse((Path(folder)/'turn-000/intent.private.json').exists())
   self.assertTrue((Path(folder)/'turn-000/nonce.private.json').exists());self.assertIsNone(active.latest);guard.close()
