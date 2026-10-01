"""Uniform reset calls the proved boot/teardown path for every episode."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gitlab_world import v066_uniform_task_runtime_v12 as world
from tests import test_gitlab_neutral_telemetry_coldboot_v5 as cold_tests
from tests.test_gitlab_neutral_telemetry_coldboot_v1 import snapshot

class Backend:
 def __init__(self):self.calls=[];self.owned_cycles=set();self.doc={'container_prefix':'owned'};self.changed=False
 def protected(self):return {'old':'same'}
 def seed_content(self):return {'seed':'same'}
 def record(self,*args):self.calls.append(('record',args[0]))
 def boot(self,index):
  self.calls.append(('boot',index));self.owned_cycles.add(index)
  return {'state_snapshot':snapshot(),'effective_settings':world.cold.EXPECTED_SETTINGS,'full_git_trees':{},'container_id_sha256':str(index+1)*64,
   'services':{s:'running' for s in world.cold.profile.CRITICAL_SERVICES}|{s:'absent' for s in world.cold.profile.OPTIONAL_SERVICES}}
 def teardown(self,index):self.calls.append(('teardown',index));return {'owned_container_absent':True}

class ResetTests(unittest.TestCase):
 def test_every_reset_uses_fresh_boot_and_previous_owned_teardown(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);state=root/'cow-reset-state.json';state.write_text(json.dumps({'clone_generation':0}));state.chmod(0o600)
   backend=Backend();value=world.TaskWorld(root/'plan',root/'permit',root,phase='full-study');value.backend=backend
   value.before={'full_git_trees':{}};value.protected_before=backend.protected();value.seed_before=backend.seed_content()
   with patch.object(world.reset,'_baseline',return_value=snapshot()),patch.object(world.reset,'STATE_FILE',state),patch.object(world.runtime,'WORLD','old'):
    first=value.reset();second=value.reset()
    self.assertEqual(world.runtime.WORLD,'owned-1');self.assertEqual(first['generation'],1);self.assertEqual(second['generation'],2)
   self.assertEqual([x for x in backend.calls if x[0] in ['boot','teardown']],[('boot',0),('teardown',0),('boot',1)])
   self.assertEqual(json.loads(state.read_bytes())['clone_generation'],2)
 def test_partial_boot_failure_cleans_only_claimed_generation(self):
  backend=Backend();value=world.TaskWorld(Path('plan'),Path('permit'),Path('artifact'),phase='full-study');value.backend=backend
  def failed(index):backend.owned_cycles.add(index);raise RuntimeError('cold boot failed')
  with patch.object(backend,'boot',side_effect=failed):
   with self.assertRaises(RuntimeError):value.reset()
  self.assertIn(('teardown',0),backend.calls);self.assertEqual(value.generation,0)
 def test_sql_git_profile_and_seed_changes_fail_before_actor(self):
  for field in ['state_snapshot','effective_settings','full_git_trees']:
   backend=Backend();value=world.TaskWorld(Path('plan'),Path('permit'),Path('artifact'),phase='full-study');value.backend=backend
   value.before={'full_git_trees':{}};value.protected_before=backend.protected();value.seed_before=backend.seed_content();cycle=backend.boot(0)
   cycle[field]={'changed':True} if field!='full_git_trees' else {'1':{'refs/heads/main':{'commit':'x','tree_sha256':'y'}}}
   with patch.object(backend,'boot',return_value=cycle),patch.object(world.reset,'_baseline',return_value=snapshot()):
    with self.assertRaises((ValueError,KeyError)):value.reset()
   self.assertEqual(value.generation,0)

if __name__=='__main__':unittest.main()

from tests import test_gitlab_neutral_telemetry_coldboot_v3 as attrs_tests
from tests import test_gitlab_neutral_telemetry_coldboot_v4 as layers_tests
from gitlab_world import v066_neutral_telemetry_coldboot_v5 as cold
from unittest.mock import MagicMock

class ActualBootPathTests(unittest.TestCase):
 def test_two_task_resets_call_proved_mount_upper_env_and_native_reader_path(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);doc={'container_prefix':'envloop-gitlab-neutral-telemetry-'+'a'*12,'vm_root':'/var/lib/envloop-gitlab-neutral-telemetry-'+'a'*12,
    'neutral_base':'http://127.0.0.1:8018','port':8018,'source_sha256s':{},'seed_lowerdirs':{r:'/immutable/'+r for r in world.runtime.DESTS}}
   cold.write_raw(root/'neutral-runtime.env',b'SVWAIT=60\n')
   state=root/'state.json';state.write_text('{}');state.chmod(0o600)
   backend=cold.NativeBackend(doc,root);backend.parent_claim={'inode':1,'device':1}
   native=attrs_tests.attrs();native['all_observed_attribute_layers']={layer:{k:v[layer] for k,v in native['fixed_settings'].items()} for layer in ['normal','default']}
   native['unknown_service_value_layers']=[];calls=[];mounts=[]
   def docker(*args,**kwargs):
    calls.append(args)
    if args[0]=='inspect':return json.dumps({'Running':True,'StartedAt':attrs_tests.START})
    if args[0]=='exec' and args[2]=='gitlab-ctl':return '\n'.join('run: '+s+': (pid 1) 1s' for s in cold.profile.CRITICAL_SERVICES)
    if args[0]=='exec':return json.dumps(native)
    return 'owned'
   value=world.TaskWorld(root/'plan',root/'permit',root,phase='full-study');value.backend=backend;value.before={'full_git_trees':{}};value.protected_before={'old':'same'};value.seed_before={'lower':'same'}
   with cold.version_scope(),patch.object(backend,'vm',side_effect=lambda script,**kw:mounts.append(script) or ''),\
    patch.object(backend,'container_exists',return_value=False),patch.object(backend,'configure_upper',return_value={'exact_suffix_only':True}) as upper,\
    patch.object(backend,'docker',side_effect=docker),patch.object(backend,'capture_logs'),patch.object(backend,'git_trees',return_value={}),\
    patch.object(backend,'protected',return_value=value.protected_before),patch.object(backend,'seed_content',return_value=value.seed_before),\
    patch.object(backend,'teardown',return_value={}) as teardown,patch.object(cold.legacy.scoped,'wait_cohort',side_effect=[{'container_id_sha256':'1'*64,'image_ref':world.runtime.IMAGE,'image_id':world.runtime.IMAGE_ID,'mounts':{},'ports':{},'running':True,'health':'healthy'}, {'container_id_sha256':'2'*64,'image_ref':world.runtime.IMAGE,'image_id':world.runtime.IMAGE_ID,'mounts':{},'ports':{},'running':True,'health':'healthy'}]),\
    patch.object(world.verify,'state_snapshot',return_value=snapshot()),patch.object(world.runtime,'inspect',return_value={'Config':{'Env':['SVWAIT=60']},'HostConfig':{'RestartPolicy':{'Name':'no','MaximumRetryCount':0}}}),\
    patch.object(world.reset,'_baseline',return_value=snapshot()),patch.object(world.reset,'STATE_FILE',state),patch.object(world.runtime,'WORLD','old'):
     value.reset();value.reset()
   self.assertEqual(upper.call_count,2);teardown.assert_called_once_with(0)
   self.assertEqual(sum('mount -t overlay' in script for script in mounts),6)
   self.assertEqual(sum(c[0]=='run' for c in calls),2)
   self.assertTrue(all('127.0.0.1:8018:8018' in c for c in calls if c[0]=='run'))
   self.assertEqual(len(list(root.glob('cycle-*-native-attributes.private.json'))),2)
