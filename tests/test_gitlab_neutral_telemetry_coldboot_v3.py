"""Poststartup native node attributes without Cinc or config mutation."""
import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gitlab_world import v066_neutral_telemetry_coldboot_v3 as v3
from tests.test_gitlab_neutral_telemetry_coldboot_v1 import FixtureBackend,snapshot,identity
from tests import test_gitlab_neutral_telemetry_coldboot_v2 as v2_tests

START='2026-10-01T00:00:00.123456789Z'

def attrs():
 rows={k:{'normal':{'present':True,'type':'FalseClass','boolean':False},'default':{'present':True,'type':'TrueClass','boolean':True},
  'override':{'present':False,'type':'Absent'}} for k in v3.SETTINGS_PATHS}
 return {'schema':'envloop-gitlab18.5-native-node-settings-v1','parse_status':True,'node_name_exact':True,'artifact_regular_nonsymlink':True,
  'artifact_bytes':1000,'artifact_sha256':'a'*64,'artifact_mtime_ns':v3.docker_started_ns(START)+1000000000,
  'fixed_paths':copy.deepcopy(v3.SETTINGS_PATHS),'fixed_settings':rows,'effective_settings':copy.deepcopy(v3.EXPECTED_SETTINGS)}

class AttributeTests(unittest.TestCase):
 def test_native_normal_values_override_true_defaults_and_require_fresh_artifact(self):
  self.assertTrue(v3.validate_attributes(attrs(),started_at=START)['native_all_nine_false'])
  self.assertEqual(v3.docker_started_ns(START)%1000000000,123456789)
 def test_stale_name_schema_missing_normal_type_and_override_fail(self):
  for attack in ['stale','name','schema','missing','type','override','path']:
   with self.subTest(attack=attack):
    value=copy.deepcopy(attrs());key="node_exporter['enable']"
    if attack=='stale':value['artifact_mtime_ns']=v3.docker_started_ns(START)-1
    elif attack=='name':value['node_name_exact']=False
    elif attack=='schema':value['parse_status']=False
    elif attack=='missing':value['fixed_settings'][key]['normal']={'present':False,'type':'Absent'}
    elif attack=='type':value['fixed_settings'][key]['normal']={'present':True,'type':'String'}
    elif attack=='override':value['fixed_settings'][key]['override']={'present':True,'type':'TrueClass','boolean':True}
    else:value['fixed_paths'][key]=['unknown','node_exporter','enable']
    with self.assertRaises(ValueError):v3.validate_attributes(value,started_at=START)
 def test_plain_reader_real_file_retains_only_fixed_values_and_leaves_bytes_metadata(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'node.json';node={'name':v3.NODE_NAME,'normal':{},'default':{},'private_secret':'must-never-leave'}
   for names in v3.SETTINGS_PATHS.values():
    for layer,value in [('normal',False),('default',True)]:
     root=node[layer]
     for name in names[:-1]:root=root.setdefault(name,{})
     root[names[-1]]=value
   path.write_text(json.dumps(node));before=path.read_bytes();stat=path.stat()
   script=v3.node_reader_ruby().replace(v3.NODE_PATH,str(path))
   result=subprocess.run(['ruby','-e',script],capture_output=True,text=True,check=True)
   self.assertNotIn('must-never-leave',result.stdout+result.stderr);value=json.loads(result.stdout)
   self.assertEqual(value['effective_settings'],v3.EXPECTED_SETTINGS);self.assertTrue(value['node_name_exact'])
   self.assertEqual(path.read_bytes(),before);self.assertEqual(path.stat().st_mtime_ns,stat.st_mtime_ns)
   self.assertNotIn('show-config',script);self.assertNotIn('generate_config',script)
 def test_original_default_projection_is_not_false_profile_credit(self):
  value=attrs()
  for key in value['fixed_settings']:
   value['fixed_settings'][key]['normal']={'present':False,'type':'Absent'}
   value['effective_settings'][key]=True
  with self.assertRaises(ValueError):v3.validate_attributes(value,started_at=START)
 def test_native_boot_saves_sql_before_later_attribute_failure_and_never_calls_cinc(self):
  doc=v2_tests.SeamTests().doc()|{'neutral_base':'http://127.0.0.1:8026','seed_lowerdirs':{r:'/immutable/'+r for r in v3.runtime.DESTS}}
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);v3.write_raw(root/'neutral-runtime.env',b'SVWAIT=60\n');backend=v3.NativeBackend(doc,root)
   backend.parent_claim={'inode':1,'device':1};calls=[];bad=attrs();bad['parse_status']=False
   def docker(*args,**kwargs):
    calls.append(args)
    if args[0]=='inspect':return json.dumps({'Running':True,'StartedAt':START})
    if args[:3]==('exec',doc['container_prefix']+'-0','gitlab-ctl'):return '\n'.join('run: '+s+': (pid 1) 1s' for s in v3.profile.CRITICAL_SERVICES)
    if args[0]=='exec':return json.dumps(bad)
    return 'new-id'
   with patch.object(backend,'container_exists',return_value=False),patch.object(backend,'vm',return_value=''),\
    patch.object(backend,'configure_upper',return_value={'exact_suffix_only':True}),patch.object(backend,'docker',side_effect=docker),\
    patch.object(backend,'capture_logs'),patch.object(backend,'git_trees',return_value={}),\
    patch.object(v3.legacy.scoped,'wait_cohort',return_value=identity('1')|{'running':True,'health':'healthy'}),\
    patch.object(v3.legacy.verify,'state_snapshot',return_value=snapshot()),patch.object(v3.runtime,'inspect',return_value={'Config':{'Env':['SVWAIT=60']},'HostConfig':{'RestartPolicy':{'Name':'no','MaximumRetryCount':0}}}):
     with self.assertRaises(ValueError):backend.boot(0)
   self.assertEqual(json.loads((root/'cycle-0-snapshot.private.json').read_bytes()),snapshot())
   self.assertTrue((root/'cycle-0-native-attributes.private.json').exists())
   self.assertEqual(sum(args[0]=='run' for args in calls),1)
   self.assertFalse(any('show-config' in str(args) or 'reconfigure' in str(args) for args in calls))
 def test_saved_audit_reopens_native_attribute_projection(self):
  helper=v2_tests.SeamTests();helper.addCleanup=self.addCleanup
  backend,root,plan,permit=helper.fixture()
  # Fixture TemporaryDirectory remains alive via helper cleanup closure.
  state=json.loads((root/'cycle-0-state.private.json').read_bytes())
  for index in range(3):
   state['StartedAt']=START;(root/f'cycle-{index}-state.private.json').write_text(json.dumps(state))
   v3.write_raw(root/f'cycle-{index}-native-attributes.private.json',json.dumps(attrs()).encode())
  result=json.loads(v3.source.private(root/'result.private.json'));result['raw_file_sha256s']=v3.raw_refs(root)
  (root/'result.private.json').write_bytes(v3.factory.canonical(result))
  with patch.object(v3,'checked_plan',return_value=(backend.doc,{},snapshot())):result=v3.audit(plan=plan,permit=permit)
  self.assertEqual(result['neutral_cycles_verified'],3);self.assertEqual(result['control_credit'],0)
 def test_frozen_v1_v2_bytes_and_version_globals_remain_unchanged(self):
  self.assertEqual(v3.source.sha(Path(v3.previous.__file__).read_bytes()),v3.PINNED_V2)
  self.assertEqual(v3.source.sha(Path(v3.legacy.__file__).read_bytes()),v3.previous.PINNED_V1)
  before=v3.legacy.SCHEMA
  with v3.version_scope():self.assertEqual(v3.legacy.SCHEMA,v3.SCHEMA)
  self.assertEqual(v3.legacy.SCHEMA,before)

if __name__=='__main__':unittest.main()
