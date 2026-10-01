"""Offline lifecycle controls plus an opt-in replay of an actual TRAIN package."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from tools import office_owned_folder_runtime_v2 as rt
from ppt_wdi_factory import verify
from cursibench import native_surface_guard_policy_v1 as policy


def put(path,raw):
 path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 path.write_bytes(raw);path.chmod(0o600);return {'path':path.name,'sha256':rt.sha(raw)}

class FixturePackage:
 actor=rt.ActorTask('fixture-train','e'*64,'powerpoint-web','train','Visible task only','f'*64)
 binding_sha256='e'*64
 def __init__(self,source):self.paths={'baseline':source}
 def actor_projection(self):return dict(self.actor.__dict__)
 def neutral(self,path):return {'equivalent':path.read_bytes()==b'neutral source'}
 def strict_score(self,path):return {'score':float(path.read_bytes()==b'correct saved'), 'raw_strict':{},'native_metadata_normalization_applied':False}

class Host:
 def __init__(self,root,binding):self.root=root;self.binding=binding;self.calls=[];self.items=[];self.n=0;self.fail=None;self.mismatch=False;self.saved=False
 def capabilities(self):return {'surface':'original-office-web','same_account':True,'graph':False,'offline_fixture':True}
 def record(self,op,**extra):
  self.calls.append(op)
  if self.fail==op:raise rt.OfficeRuntimeError('fixture unknown operation')
  self.n+=1;refs=[]
  for k in range(2):refs.append(put(self.root/f'raw-{self.n}-{k}.private',f'offline fixture {op} {k}'.encode()))
  return {'schema':'office-owned-folder-native-operation-v2','operation':op,'account_principal_sha256':self.binding['account_principal_sha256'],
   'folder_scope_sha256':self.binding['folder_scope_sha256'],'native_ui':True,'graph_used':False,'new_account_used':False,'status':'completed','raw_refs':refs,**extra}
 def owned_folder_inventory(self):return self.record('folder_inventory',items=copy.deepcopy(self.items))
 def create_from_baseline(self,task,baseline,*,purpose):
  item={'account_principal_sha256':self.binding['account_principal_sha256'],'folder_scope_sha256':self.binding['folder_scope_sha256'],'item_identity_sha256':rt.sha(str(self.n).encode()),'purpose':purpose}
  rec=self.record('create_document',item=item);self.items.append(item);return rec
 def double_download(self,item,*,purpose):
  raw=b'correct saved' if self.saved and item['purpose']=='actor' and purpose in ['saved_actor','explicit_saved_readback'] else b'neutral source'
  refs=[put(self.root/f'download-{self.n}-{k}.pptx',raw+(b'bad' if self.mismatch and k else b'')) for k in range(2)]
  return self.record('double_download',item_identity_sha256=item['item_identity_sha256'],download_refs=refs)
 def actor_open(self,*args,**kwargs):
  class Actor:native_policy_sha256=policy.POLICY_SHA
  return Actor()
 def close_document(self,item):return self.record('close_document',item_identity_sha256=item['item_identity_sha256'])
 def remove_owned_item(self,item):
  rec=self.record('remove_document',item_identity_sha256=item['item_identity_sha256']);self.items.remove(item);return rec

class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
  self.evidence=self.root/'evidence';self.evidence.mkdir(mode=0o700)
  self.binding={'schema':rt.SCHEMA,'single_account':True,'scope':'existing_account_dedicated_disposable_folder','source_sha256s':rt.source_hashes(),'native_policy_sha256':policy.POLICY_SHA,
   'account_principal_sha256':rt.sha(str(self.root).encode()),'folder_scope_sha256':'b'*64,'native_evidence_root':str(self.evidence),'cells':['powerpoint-web'],'splits':['train'],'max_wall_seconds':600}
  self.bp=self.root/'binding.private.json';put(self.bp,rt.canonical(self.binding));self.pp=self.root/'permit.private.json';put(self.pp,rt.canonical({'schema':'office-owned-folder-runtime-permit-v2','binding_sha256':rt.sha(self.bp.read_bytes()),'source_reviewed':True}))
  self.source=self.root/'source.pptx';put(self.source,b'neutral source');self.package=FixturePackage(self.source);self.host=Host(self.evidence,self.binding)
 def tearDown(self):
  lease=rt.AccountLease(self.binding['account_principal_sha256'],expires_at_ms=0)
  if lease.path.exists():lease.path.unlink()
  self.temp.cleanup()
 def runtime(self,mode='offline_fixture'):return rt.Runtime(self.host,binding_path=self.bp,permit_path=self.pp,artifact_root=self.root/'attempt',mode=mode)
 def test_double_saved_readback_and_fresh_reset(self):
  runtime=self.runtime()
  with runtime.open(self.package,attempt_id='one') as session:
   self.host.saved=True;self.assertEqual(session.read_saved_state()['score'],1)
  self.assertEqual(session.saved_score['score'],1);self.assertEqual(self.host.calls.count('create_document'),2)
  self.assertEqual(self.host.items,[]);self.assertFalse(runtime.account_lease.path.exists())
  self.assertTrue((runtime.root/'reset-score.private.json').exists())
 def test_unqualified_fixture_cannot_launch_native(self):
  with self.assertRaisesRegex(rt.OfficeRuntimeError,'unqualified'):self.runtime('native')
  self.assertEqual(self.host.calls,[])
 def test_foreign_item_never_removed_or_reset(self):
  self.host.items=[{'foreign':True}];runtime=self.runtime()
  with self.assertRaisesRegex(rt.OfficeRuntimeError,'start empty'):
   with runtime.open(self.package,attempt_id='one'):pass
  self.assertEqual(self.host.calls,['folder_inventory']);self.assertFalse(runtime.account_lease.path.exists())
 def test_unknown_create_keeps_account_handle_no_retry(self):
  self.host.fail='create_document';runtime=self.runtime()
  with self.assertRaisesRegex(rt.OfficeRuntimeError,'creation uncertain'):
   with runtime.open(self.package,attempt_id='one'):pass
  self.assertEqual(self.host.calls.count('create_document'),1);self.assertTrue(runtime.account_lease.path.exists())
 def test_unstable_download_fails_but_owned_cleanup_runs(self):
  self.host.mismatch=True;runtime=self.runtime()
  with self.assertRaisesRegex(rt.OfficeRuntimeError,'stabilize'):
   with runtime.open(self.package,attempt_id='one'):pass
  self.assertEqual(self.host.items,[]);self.assertFalse(runtime.account_lease.path.exists())
 def test_delete_failure_keeps_unknown_handle_and_never_retries(self):
  runtime=self.runtime();self.host.fail='remove_document'
  with self.assertRaises(rt.OfficeRuntimeError):
   with runtime.open(self.package,attempt_id='one'):pass
  self.assertEqual(self.host.calls.count('remove_document'),1);self.assertTrue(runtime.account_lease.path.exists())
 def test_shared_account_lease_collides_across_roots_and_expiry(self):
  lease=rt.AccountLease(self.binding['account_principal_sha256'],expires_at_ms=int(time.time()*1000)+60000);lease.acquire()
  other=rt.AccountLease(self.binding['account_principal_sha256'],expires_at_ms=int(time.time()*1000)+90000)
  with self.assertRaisesRegex(rt.OfficeRuntimeError,'no automatic'):other.acquire()
  lease.release()
 def test_source_tamper_fails_before_host_calls(self):
  self.binding['source_sha256s']['tools/office_owned_folder_runtime_v2.py']='0'*64;put(self.bp,rt.canonical(self.binding));put(self.pp,rt.canonical({'schema':'office-owned-folder-runtime-permit-v2','binding_sha256':rt.sha(self.bp.read_bytes()),'source_reviewed':True}))
  with self.assertRaisesRegex(rt.OfficeRuntimeError,'closure'):self.runtime()
  self.assertEqual(self.host.calls,[])

@unittest.skipUnless(os.environ.get('ENVLOOP_PPT_TRAIN_PACKAGE'),'actual TRAIN package path not configured')
class ActualTrainTests(unittest.TestCase):
 def test_current_package_actor_projection_and_real_adverse_scoring(self):
  source=Path(os.environ['ENVLOOP_PPT_TRAIN_PACKAGE']);task=json.loads((source/'task.private.json').read_bytes())
  self.assertIn(task['split'],['train','train_policy_development'])
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);root.chmod(0o700)
   for name in ['source.pptx','task.private.json','source-snapshot.private.json','source-provenance.private.json','source-country.private.zip']:
    if (source/name).exists():put(root/name,(source/name).read_bytes())
   descriptor=root/'package.private.json';rt.descriptor(cell_id='powerpoint-web',split=task['split'],task_id=task['task_id'],instruction=task['actor_task'],baseline=root/'source.pptx',task_spec=root/'task.private.json',out=descriptor)
   package=rt.Package(descriptor,package_root=root);self.assertEqual(set(package.actor_projection()),{'task_id','package_sha256','cell_id','split','visible_instruction','baseline_sha256'})
   self.assertTrue(package.neutral(package.paths['baseline'])['equivalent']);self.assertEqual(package.strict_score(package.paths['baseline'])['score'],0)
   correct={k:v['correct'] for k,v in package.oracle['targets'].items()}
   for name,changes,collateral,chart in [('positive',correct,False,False),('wrong',{},False,False),('collateral',correct,True,False),('chart',correct,False,True)]:
    candidate=root/(name+'.pptx');verify._write_variant(package.paths['baseline'],candidate,changes,package.oracle,collateral=collateral,chart_damage=chart)
    score=package.strict_score(candidate);self.assertEqual(score['score'],int(name=='positive'));self.assertFalse(score['native_metadata_normalization_applied'])

if __name__=='__main__':unittest.main()
