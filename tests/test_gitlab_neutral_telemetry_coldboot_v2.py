"""Exact CLI response and stable native manifest regressions; no native calls."""
import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gitlab_world import v066_neutral_telemetry_coldboot_v2 as v2
from tests.test_gitlab_neutral_telemetry_coldboot_v1 import FixtureBackend,snapshot

NAME='envloop-gitlab-neutral-telemetry-'+'a'*12+'-0'

class SeamTests(unittest.TestCase):
 def doc(self):return {'port':8026,'internal_port':8018,'container_prefix':NAME[:-2],'vm_root':'/var/lib/'+NAME[:-2],
  'protected_bound_metadata_sha256s':{},'original_metadata_sha256s':{'runtime.env':'d'*64},'frozen_source_sha256s':{'verify.py':'e'*64},'source_sha256s':{'new.py':'f'*64}}
 def test_exact_uppercase_lowercase_absence_only(self):
  for raw in [('error: no such object: '+NAME+'\n').encode(),('Error: No such object: '+NAME+'\n').encode()]:
   self.assertTrue(v2.known_absence(1,b'\n',raw,NAME))
  bad=[b'Cannot connect to the Docker daemon',b'context not found',b'operation timed out',
   ('error: no such object: '+NAME+'-other\n').encode(),('daemon error\nerror: no such object: '+NAME+'\n').encode(),b'No such object: '+NAME.encode()]
  for raw in bad:self.assertFalse(v2.known_absence(1,b'',raw,NAME))
  for code in [0,2,None,True]:self.assertFalse(v2.known_absence(code,b'',('error: no such object: '+NAME).encode(),NAME))
  self.assertFalse(v2.known_absence(1,b'unexpected output',('error: no such object: '+NAME).encode(),NAME))
 def test_backend_reopens_lowercase_raw_and_preserves_it_exactly(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);raw=('error: no such object: '+NAME+'\n').encode();backend=v2.NativeBackend(self.doc(),root)
   with patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'\n',raw)):
    self.assertFalse(backend.container_exists(NAME,'cycle-0-preexisting.private.json'))
   self.assertEqual((root/'cycle-0-preexisting.private.json.stderr.private.log').read_bytes(),raw)
 def test_timeout_retains_raw_and_never_proves_absence(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);backend=v2.NativeBackend(self.doc(),root)
   with patch.object(subprocess,'run',side_effect=subprocess.TimeoutExpired([],30,output=b'partial',stderr=b'daemon delayed')):
    with self.assertRaises(subprocess.TimeoutExpired):backend.container_exists(NAME,'cycle-0-preexisting.private.json')
   row=json.loads((root/'cycle-0-preexisting.private.json').read_bytes());self.assertIsNone(row['returncode']);self.assertTrue(row['timed_out'])
   self.assertEqual((root/'cycle-0-preexisting.private.json.stderr.private.log').read_bytes(),b'daemon delayed')
 def test_present_identity_requires_valid_exact_docker_id(self):
  for raw,good in [(b'1'*64+b'\n',True),(b'partial',False)]:
   with tempfile.TemporaryDirectory() as folder:
    backend=v2.NativeBackend(self.doc(),Path(folder))
    with patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],0,raw,b'')):
     if good:self.assertTrue(backend.container_exists(NAME,'cycle-0-preexisting.private.json'))
     else:
      with self.assertRaises(ValueError):backend.container_exists(NAME,'cycle-0-preexisting.private.json')
 def test_scope_is_native_owned_and_wrapper_sibling_can_keep_growing(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);native=root/'native';wrapper=root/'supervision';native.mkdir();wrapper.mkdir()
   v2.write_raw(native/'plan.private.json',b'{}');v2.write_raw(native/'cycle-0-state.private.json',b'{}')
   before=v2.raw_refs(native);(wrapper/'worker.stdout.private.log').write_bytes(b'initial')
   (wrapper/'worker.stdout.private.log').write_bytes(b'initial\nresult\n');(wrapper/'supervisor-terminal.private.json').write_bytes(b'{}')
   self.assertEqual(v2.raw_refs(native),before)
   v2.write_raw(native/'worker.stdout.private.log',b'contamination')
   with self.assertRaises(ValueError):v2.raw_refs(native)
 def test_contaminated_scope_fails_before_any_native_factory(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);v2.write_raw(root/'plan.private.json',b'{}');v2.write_raw(root/'worker.stdout.private.log',b'changing')
   with patch.object(v2,'NativeBackend') as native:
    with self.assertRaises(ValueError):v2.run(plan=root/'plan.private.json',permit=root/'permit.private.json',execute=True,backend_factory=native)
    native.assert_not_called()
 def test_scope_rejects_unowned_links_or_unknown_files(self):
  for kind in ['link','unknown','directory']:
   with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);v2.write_raw(root/'plan.private.json',b'{}')
    if kind=='link':(root/'cycle-0-state.private.json').symlink_to(root/'plan.private.json')
    elif kind=='directory':(root/'nested').mkdir()
    else:v2.write_raw(root/'unknown.private.json',b'{}')
    with self.assertRaises(ValueError):v2.raw_refs(root)
 def fixture(self):
  folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);root=Path(folder.name);doc=self.doc();backend=FixtureBackend(doc,root)
  plan=root/'plan.private.json';permit=root/'permit.private.json';v2.source.write_new(plan,doc)
  v2.source.write_new(permit,{'accepted':True,'plan_sha256':v2.source.sha(v2.source.private(plan)),'source_sha256s':doc['source_sha256s']})
  v2.source.write_new(root/'run-intent.private.json',{'plan_sha256':v2.source.sha(v2.source.private(plan)),
   'permit_sha256':v2.source.sha(v2.source.private(permit)),'worker_and_lease_proof':{'old_worker_processes':0,'supervisor_locks_exclusive':True}})
  result=v2.legacy.execute_cycles(doc,snapshot(),backend)
  for index in range(3):
   path=root/f'cycle-{index}-post-teardown.private.json.stderr.private.log'
   path.write_bytes(('error: no such object: '+doc['container_prefix']+'-'+str(index)+'\n').encode())
   v2.write_raw(root/f'cycle-{index}-post-teardown.private.json.stdout.private.log',b'\n')
  result['raw_file_sha256s']=v2.raw_refs(root);v2.source.write_new(root/'result.private.json',result)
  return backend,root,plan,permit
 def test_v2_saved_audit_replays_lowercase_absence_and_stable_scope(self):
  backend,root,plan,permit=self.fixture()
  with patch.object(v2,'checked_plan',return_value=(backend.doc,{},snapshot())):result=v2.audit(plan=plan,permit=permit)
  self.assertEqual(result['neutral_cycles_verified'],3);self.assertEqual(result['control_credit'],0)
 def test_forged_wrong_object_absence_fails_even_with_updated_manifest(self):
  backend,root,plan,permit=self.fixture();path=root/'cycle-0-post-teardown.private.json.stderr.private.log';path.write_bytes(b'error: no such object: other\n')
  result=json.loads(v2.source.private(root/'result.private.json'));result['raw_file_sha256s']=v2.raw_refs(root)
  (root/'result.private.json').write_bytes(v2.legacy.factory.canonical(result))
  with patch.object(v2,'checked_plan',return_value=(backend.doc,{},snapshot())):
   with self.assertRaises(ValueError):v2.audit(plan=plan,permit=permit)
 def test_v1_source_is_pinned_and_scope_restores_legacy_globals(self):
  before={name:getattr(v2.legacy,name) for name in ['SCHEMA','SOURCE_FILES','raw_refs']}
  self.assertEqual(v2.source.sha(Path(v2.legacy.__file__).read_bytes()),v2.PINNED_V1)
  with v2.version_scope():self.assertEqual(v2.legacy.SCHEMA,v2.SCHEMA);self.assertIs(v2.legacy.raw_refs,v2.raw_refs)
  for name,value in before.items():self.assertEqual(getattr(v2.legacy,name),value)

if __name__=='__main__':unittest.main()
