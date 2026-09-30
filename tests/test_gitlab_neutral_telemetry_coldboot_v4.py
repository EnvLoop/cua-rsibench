"""Ordered live-dependency stop and immutable failure/restoration contracts."""
import copy,json,subprocess,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from gitlab_world import v066_neutral_telemetry_coldboot_v4 as v4
from tests.test_gitlab_neutral_telemetry_coldboot_v1 import FixtureBackend,snapshot,identity
from tests import test_gitlab_neutral_telemetry_coldboot_v2 as v2_tests
from tests import test_gitlab_neutral_telemetry_coldboot_v3 as v3_tests


def statuses(sidekiq='running',postgresql='running',redis='running'):
 return {s:'running' for s in v4.profile.CRITICAL_SERVICES}|{'sidekiq':sidekiq,'postgresql':postgresql,'redis':redis}

def raw_status(sidekiq='run'):
 return ('run: postgresql: (pid 1) 1s\nrun: redis: (pid 2) 1s\n'+sidekiq+': sidekiq: (pid 3) 1s\n').encode()

class OrderedTests(unittest.TestCase):
 def test_known_down_return0_or1_is_physical_down_not_healthy(self):
  for code in [0,1]:
   value=v4.status_semantics(code,raw_status('down'),b'');self.assertEqual(value['sidekiq'],'disabled');self.assertEqual(value['postgresql'],'running')
  for code,stdout,stderr in [(1,raw_status(),b''),(1,b'',b'daemon unavailable'),(2,raw_status('down'),b''),(0,b'fail: sidekiq: unknown\n',b'')]:
   with self.assertRaises(ValueError):v4.status_semantics(code,stdout,stderr)
 def test_real_status_reader_retains_nonzero_known_down_and_unknown_error_exit(self):
  for good in [True,False]:
   with tempfile.TemporaryDirectory() as folder:
    root=Path(folder);backend=v4.NativeBackend(v2_tests.SeamTests().doc(),root)
    result=subprocess.CompletedProcess([],1,raw_status('down') if good else b'',b'' if good else b'context unavailable')
    with patch.object(subprocess,'run',return_value=result):
     if good:self.assertEqual(backend.service_status('owned','original-ordered-sidekiq-after')['services']['sidekiq'],'disabled')
     else:
      with self.assertRaises(ValueError):backend.service_status('owned','original-ordered-sidekiq-after')
    row=json.loads((root/'original-ordered-sidekiq-after.private.json').read_bytes());self.assertEqual(row['returncode'],1);self.assertEqual(row['semantic_status_valid'],good)
 def test_actual_original_call_path_stops_sidekiq_before_docker_and_preserves_dependencies(self):
  with tempfile.TemporaryDirectory() as folder:
   doc=v2_tests.SeamTests().doc()|{'original_container':'preserved33'};backend=v4.NativeBackend(doc,Path(folder));calls=[]
   before={'identity':identity()}
   def docker(*args,**kwargs):
    calls.append(args)
    if args[0]=='inspect':return json.dumps({'Running':False,'ExitCode':0,'OOMKilled':False})
    return ''
   with patch.object(backend,'service_status',side_effect=[{'services':statuses()},{'services':statuses(sidekiq='disabled')}]),\
    patch.object(backend,'docker',side_effect=docker),patch.object(v4.runtime,'proof',return_value=identity()|{'running':False}):backend.stop_original(before)
   self.assertEqual(calls[0],('exec','preserved33','gitlab-ctl','stop','sidekiq'))
   self.assertEqual(calls[1],('stop','--time','300','preserved33'))
   self.assertTrue(backend.original_sidekiq_stop_attempted)
 def test_dead_dependency_refuses_named_stop_without_native_mutation(self):
  with tempfile.TemporaryDirectory() as folder:
   backend=v4.NativeBackend(v2_tests.SeamTests().doc()|{'original_container':'original'},Path(folder))
   with patch.object(backend,'service_status',return_value={'services':statuses(redis='disabled')}),patch.object(backend,'docker') as docker:
    with self.assertRaises(ValueError):backend.ordered_sidekiq_stop('original','original-ordered-sidekiq')
    docker.assert_not_called()
 def test_original_failed_named_stop_rolls_back_sidekiq_once_and_never_boots(self):
  class Mixed(v4.NativeBackend,FixtureBackend):pass
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);doc=v2_tests.SeamTests().doc()|{'original_container':'original'};backend=Mixed(doc,root);state={'sidekiq':True};commands=[]
   def status(name,label):return {'services':statuses(sidekiq='running' if state['sidekiq'] else 'disabled')}
   def docker(*args,**kwargs):
    commands.append(args)
    if args[-3:]==('gitlab-ctl','stop','sidekiq'):state['sidekiq']=False;raise RuntimeError('named stop returned failure')
    if args[-3:]==('gitlab-ctl','start','sidekiq'):state['sidekiq']=True
    return ''
   with patch.object(backend,'service_status',side_effect=status),patch.object(backend,'docker',side_effect=docker),\
    patch.object(v4.runtime,'proof',return_value=identity()|{'running':True}):
     with self.assertRaises(RuntimeError):v4.legacy.execute_cycles(doc,snapshot(),backend)
   self.assertTrue(state['sidekiq']);self.assertEqual(sum(a[-3:]==('gitlab-ctl','stop','sidekiq') for a in commands),1)
   self.assertEqual(sum(a[-3:]==('gitlab-ctl','start','sidekiq') for a in commands),1)
   self.assertFalse(any(k=='boot' for k,v in backend.calls));self.assertTrue(backend.running)
 def test_owned_teardown_order_failure_still_calls_frozen_cleanup_once(self):
  with tempfile.TemporaryDirectory() as folder:
   doc=v2_tests.SeamTests().doc()|{'neutral_base':'http://127.0.0.1:8026'};backend=v4.NativeBackend(doc,Path(folder));backend.owned_cycles.add(0)
   proof={'owned_container_absent':True,'owned_overlay_mounts_absent':True,'owned_vm_subtree_absent':True}
   with patch.object(backend,'container_exists',return_value=True),patch.object(backend,'docker',return_value=json.dumps({'Running':True})),\
    patch.object(backend,'ordered_sidekiq_stop',side_effect=RuntimeError('drain failed')),patch.object(v4.legacy.NativeBackend,'teardown',return_value=proof) as cleanup:
     with self.assertRaises(RuntimeError):backend.teardown(0)
     cleanup.assert_called_once_with(0)
 def test_reader_records_all_observed_layers_and_unknown_values_fail(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'node.json';node={'name':v4.previous.NODE_NAME,'normal':{},'default':{},'automatic':{'os':'linux'}}
   for names in v4.previous.SETTINGS_PATHS.values():
    for layer,value in [('normal',False),('default',True)]:
     row=node[layer]
     for part in names[:-1]:row=row.setdefault(part,{})
     row[names[-1]]=value
   for unknown in [False,True]:
    if unknown:node['force_override']={'monitoring':{'node_exporter':{'enable':False}}}
    path.write_text(json.dumps(node));script=v4.node_reader_ruby().replace(v4.previous.NODE_PATH,str(path))
    result=subprocess.run(['ruby','-e',script],capture_output=True,text=True,check=True);value=json.loads(result.stdout)
    started=datetime.fromtimestamp(path.stat().st_mtime-1,timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    self.assertIn('automatic',value['all_observed_attribute_layers'])
    if unknown:
     self.assertEqual(value['unknown_service_value_layers'],['force_override'])
     with self.assertRaises(ValueError):v4.validate_attributes(value,started_at=started)
    else:self.assertTrue(v4.validate_attributes(value,started_at=started)['native_all_nine_false'])
 def test_saved_audit_reopens_ordered_stop_and_rejects_other_container_command(self):
  helper=v2_tests.SeamTests();helper.addCleanup=self.addCleanup
  backend,root,plan,permit=helper.fixture();backend.doc['original_container']='preserved33'
  # Scope metadata is a fixture; the real native operation is never invoked.
  for index in range(3):
   state=json.loads((root/f'cycle-{index}-state.private.json').read_bytes());state['StartedAt']=v3_tests.START
   (root/f'cycle-{index}-state.private.json').write_text(json.dumps(state))
   value=v3_tests.attrs();value['all_observed_attribute_layers']={layer:{k:rows[layer] for k,rows in value['fixed_settings'].items()} for layer in ['normal','default']}
   value['all_observed_attribute_layers']['automatic']={k:{'present':False,'type':'Absent'} for k in value['fixed_settings']}
   value['unknown_service_value_layers']=[]
   v4.write_raw(root/f'cycle-{index}-native-attributes.private.json',json.dumps(value).encode())
   v4.write_raw(root/f'cycle-{index}-stopped-state.private.json',json.dumps({'ExitCode':0,'Running':False,'OOMKilled':False}).encode())
  for ordinal,label in enumerate(['original-ordered-sidekiq']+[f'cycle-{i}-ordered-sidekiq' for i in range(3)]):
   pairs=[]
   for phase,stdout in [('before',raw_status()),('after',raw_status('down'))]:
    row={'returncode':0,'stdout_sha256':v4.source.sha(stdout),'stderr_sha256':v4.source.sha(b''),'services':v4.status_semantics(0,stdout,b''),'semantic_status_valid':True}
    pairs.append(row);v4.write_raw(root/(label+'-'+phase+'.private.json'),json.dumps(row).encode())
    v4.write_raw(root/(label+'-'+phase+'.stdout.private.log'),stdout);v4.write_raw(root/(label+'-'+phase+'.stderr.private.log'),b'')
   name='preserved33' if ordinal==0 else backend.doc['container_prefix']+'-'+str(ordinal-1)
   command=f'command-{ordinal:03d}.private.json'
   v4.write_raw(root/command,json.dumps({'returncode':0,'argv':['docker','--context',v4.runtime.CONTEXT,'exec',name,'gitlab-ctl','stop','sidekiq']}).encode())
   v4.write_raw(root/(label+'-proof.private.json'),json.dumps({'before':pairs[0],'after':pairs[1],'sidekiq_stopped_before_dependencies':True,'stop_command_ref':command}).encode())
  restored='\n'.join('run: '+s+': (pid 1) 1s' for s in v4.profile.CRITICAL_SERVICES).encode()
  v4.write_raw(root/'original-resumed-critical.stdout.private.log',restored);v4.write_raw(root/'original-resumed-critical.stderr.private.log',b'')
  v4.write_raw(root/'original-resumed-critical.private.json',json.dumps({'returncode':0,'services':v4.status_semantics(0,restored,b'')}).encode())
  result=json.loads(v4.source.private(root/'result.private.json'));result['raw_file_sha256s']=v4.raw_refs(root)
  (root/'result.private.json').write_bytes(v4.factory.canonical(result))
  with patch.object(v4,'checked_plan',return_value=(backend.doc,{},snapshot())):
   self.assertEqual(v4.audit(plan=plan,permit=permit)['neutral_cycles_verified'],3)
  command=json.loads((root/'command-001.private.json').read_bytes());command['argv'][4]='other-owned-looking-name'
  (root/'command-001.private.json').write_text(json.dumps(command));result['raw_file_sha256s']=v4.raw_refs(root)
  (root/'result.private.json').write_bytes(v4.factory.canonical(result))
  with patch.object(v4,'checked_plan',return_value=(backend.doc,{},snapshot())):
   with self.assertRaises(ValueError):v4.audit(plan=plan,permit=permit)
 def test_version_scope_keeps_old_reader_bytes_and_restores_functions(self):
  old=v4.previous.node_reader_ruby;validator=v4.previous.validate_attributes
  self.assertEqual(v4.source.sha(Path(v4.previous.__file__).read_bytes()),v4.PINNED_V3)
  with v4.version_scope():self.assertIs(v4.previous.node_reader_ruby,v4.node_reader_ruby)
  self.assertIs(v4.previous.node_reader_ruby,old);self.assertIs(v4.previous.validate_attributes,validator)

if __name__=='__main__':unittest.main()
