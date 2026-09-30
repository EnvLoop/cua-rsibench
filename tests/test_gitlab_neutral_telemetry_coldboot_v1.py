"""Offline lifecycle/evidence attacks; none invoke Docker, Colima or a provider."""
import copy,fcntl,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gitlab_world import v066_neutral_telemetry_coldboot_v1 as probe
from gitlab_world import runtime,reset,verify

TREE=b'100644 blob '+b'1'*40+b'\tREADME.md\0'

def snapshot():
 return {'project_ids':list(range(1,34)),'git':{str(i):{'refs':{'refs/heads/main':'2'*40}} for i in range(1,34)},
  'db':{'projects':[{'id':i} for i in range(1,34)]},'business_sha256':'b'*64}

def identity(n='a'):
 return {'container_id_sha256':n*64,'image_ref':runtime.IMAGE,'image_id':runtime.IMAGE_ID,'mounts':{},'ports':{}}

class FixtureBackend(probe.NativeBackend):
 def __init__(self,doc,out,fail=None):
  super().__init__(doc,out);self.fail=fail;self.calls=[];self.snap=snapshot();self.seed={'config':{'tree_content_sha256':'c'*64,'entries':1}};self.data=b'protected';self.running=True
 def journal(self,stage,index=None):self.calls.append((stage,index));super().journal(stage,index)
 def protected(self):return {'metadata':self.doc['original_metadata_sha256s'],'core':self.doc['frozen_source_sha256s'],'ancestor_metadata':self.doc['protected_bound_metadata_sha256s'],'data_sha256':probe.source.sha(self.data)}
 def seed_content(self):return copy.deepcopy(self.seed)
 def trees(self,label):
  with patch.object(verify,'_git',return_value=TREE):return super().git_trees(self.snap,label)
 def original_before(self):
  value={'identity':identity(),'snapshot':self.snap,'full_git_trees':self.trees('original-before')};self.record('original-before.private.json',value);return value
 def stop_original(self,before):
  self.calls.append(('stop',None));self.running=False
  self.record('original-stopped.private.json',identity()|{'running':False})
  self.record('original-stopped-state.private.json',{'ExitCode':0,'OOMKilled':False})
  if self.fail=='stop':raise RuntimeError('stop proof failed')
 def boot(self,index):
  self.calls.append(('boot',index));self.owned_cycles.add(index)
  if self.fail==('boot',index):raise RuntimeError('startup logger failed')
  startup={'identity':identity(str(index+1)),'running':True,'health':'healthy','runtime_env_values_exact':True,
   'restart_policy':{'Name':'no','MaximumRetryCount':0},'SVWAIT':'60'}
  config={'exact_suffix_only':True,'suffix_sha256':probe.source.sha(probe.profile.SUFFIX.encode()),'base_sha256':'d'*64,'clone_config_sha256':'e'*64}
  services={s:'running' for s in probe.profile.CRITICAL_SERVICES}|{s:'absent' for s in probe.profile.OPTIONAL_SERVICES}
  snap=copy.deepcopy(self.snap);trees=self.trees(f'cycle-{index}')
  effective=copy.deepcopy(probe.EXPECTED_SETTINGS)
  if self.fail==('critical',index):services['postgresql']='disabled'
  if self.fail==('git',index):trees['1']['refs/heads/main']['tree_sha256']='f'*64
  if self.fail==('sql',index):snap['db']['projects'][0]['id']=999
  if self.fail==('setting',index):effective["node_exporter['enable']"]=True
  if self.fail==('seed',index):self.seed['config']['entries']=2
  if self.fail==('source',index):self.data=b'changed'
  if self.fail=='identity':startup['identity']['container_id_sha256']='1'*64
  self.record(f'cycle-{index}-startup-proof.private.json',startup)
  self.record(f'cycle-{index}-state.private.json',{'Running':True,'ExitCode':0,'OOMKilled':False,'Health':{'Status':'healthy'}})
  self.record(f'cycle-{index}-config-delta.private.json',config)
  self.record(f'cycle-{index}-effective.private.json',effective)
  probe.write_raw(self.out/f'cycle-{index}-services.private.log','\n'.join('run: '+s+': (pid 1) 1s' for s in probe.profile.CRITICAL_SERVICES).encode())
  for side in ['stdout','stderr']:probe.write_raw(self.out/f'cycle-{index}-startup.{side}.private.log',b'')
  return {'cycle':index,'healthy':True,'state_snapshot':snap,'container_id_sha256':startup['identity']['container_id_sha256'],
   'services':services,'effective_settings':effective,'full_git_trees':trees,'config_delta':config,'startup_proof':startup,
   'snapshot_ref':self.record(f'cycle-{index}-snapshot.private.json',snap)}
 def teardown(self,index):
  self.calls.append(('teardown',index))
  if self.fail==('teardown',index):raise RuntimeError('owned mount teardown failed')
  name=self.doc['container_prefix']+'-'+str(index)
  self.record(f'cycle-{index}-post-teardown.private.json',{'returncode':1})
  probe.write_raw(self.out/f'cycle-{index}-post-teardown.private.json.stderr.private.log',('Error: No such object: '+name).encode())
  value={'cycle':index,'owned_container_absent':True,'owned_overlay_mounts_absent':True,'owned_vm_subtree_absent':True,'vm_root':self.doc['vm_root']+'/cycle-'+str(index)}
  if self.fail==('remaining',index):value['owned_vm_subtree_absent']=False
  self.record(f'cycle-{index}-teardown.private.json',value);return value
 def resume_original(self,before):
  self.calls.append(('resume',None));self.running=True
  value={'same_identity':True,'exact_business_snapshot':True,'healthy':True,'identity':identity(),'snapshot':self.snap,'full_git_trees':self.trees('original-resumed')}
  self.record('original-resumed.private.json',value);return value

class NeutralTests(unittest.TestCase):
 def doc(self):return {'container_prefix':'envloop-gitlab-neutral-telemetry-'+'a'*12,'vm_root':'/var/lib/envloop-gitlab-neutral-telemetry-'+'a'*12,
  'protected_bound_metadata_sha256s':{},'original_metadata_sha256s':{'runtime.env':'d'*64},'frozen_source_sha256s':{'verify.py':'e'*64},'source_sha256s':{'new.py':'f'*64}}
 def run_fixture(self,fail=None):
  folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);root=Path(folder.name)
  backend=FixtureBackend(self.doc(),root,fail);return backend,root
 def test_three_distinct_one_boot_clones_keep_protected_bytes_and_resume(self):
  backend,_=self.run_fixture();result=probe.execute_cycles(backend.doc,snapshot(),backend)
  self.assertEqual([v for k,v in backend.calls if k=='boot'],[0,1,2]);self.assertEqual([v for k,v in backend.calls if k=='teardown'],[0,1,2])
  self.assertEqual(sum(k=='stop' for k,v in backend.calls),1);self.assertEqual(sum(k=='resume' for k,v in backend.calls),1)
  self.assertTrue(backend.running);self.assertEqual(backend.data,b'protected');self.assertEqual(result['control_credit'],0)
  self.assertTrue(result['preserved33_resume']['same_identity']);self.assertFalse(result['new_task_dispatch_authorized'])
 def test_failed_second_boot_tears_down_once_and_restores_without_third_boot(self):
  backend,_=self.run_fixture(('boot',1))
  with self.assertRaises(RuntimeError):probe.execute_cycles(backend.doc,snapshot(),backend)
  self.assertEqual([v for k,v in backend.calls if k=='boot'],[0,1]);self.assertEqual([v for k,v in backend.calls if k=='teardown'],[0,1]);self.assertTrue(backend.running)
 def test_stop_proof_failure_still_restores_and_never_boots(self):
  backend,_=self.run_fixture('stop')
  with self.assertRaises(RuntimeError):probe.execute_cycles(backend.doc,snapshot(),backend)
  self.assertFalse(any(k=='boot' for k,v in backend.calls));self.assertTrue(backend.running)
 def test_failed_teardown_still_restores_original_and_never_retries(self):
  backend,_=self.run_fixture(('teardown',0))
  with self.assertRaises(RuntimeError):probe.execute_cycles(backend.doc,snapshot(),backend)
  self.assertEqual([v for k,v in backend.calls if k=='boot'],[0]);self.assertTrue(backend.running)
 def test_sql_git_critical_profile_seed_source_and_remaining_upper_fail_closed(self):
  for kind in ['sql','git','critical','setting','seed','source','remaining']:
   with self.subTest(kind=kind):
    backend,_=self.run_fixture((kind,0))
    with self.assertRaises(ValueError):probe.execute_cycles(backend.doc,snapshot(),backend)
    self.assertEqual([v for k,v in backend.calls if k=='boot'],[0]);self.assertTrue(backend.running)
 def test_reused_container_identity_is_rejected(self):
  backend,_=self.run_fixture('identity')
  with self.assertRaises(ValueError):probe.execute_cycles(backend.doc,snapshot(),backend)
  self.assertTrue(backend.running)
 def test_real_mount_helper_and_scoping_are_used_once_per_role(self):
  doc=self.doc()|{'neutral_base':'http://127.0.0.1:8026','port':8026,'seed_lowerdirs':{r:'/immutable/'+r for r in runtime.DESTS}}
  with tempfile.TemporaryDirectory() as folder:
   out=Path(folder);probe.write_raw(out/'neutral-runtime.env',b'SVWAIT=60\n')
   backend=probe.NativeBackend(doc,out);vm=[];docker=[];old_world=runtime.WORLD;old_vm=reset.VM_ROOT
   def docker_call(*args,**kwargs):
    docker.append(args)
    if args[0]=='inspect':return json.dumps({'Running':True})
    if args[:3]==('exec',doc['container_prefix']+'-0','gitlab-ctl'):return '\n'.join('run: '+s+': (pid 1) 1s' for s in probe.profile.CRITICAL_SERVICES)
    if args[0]=='exec':return json.dumps(probe.EXPECTED_SETTINGS)
    return 'owned-created-id'
   with patch.object(backend,'container_exists',return_value=False),patch.object(backend,'vm',side_effect=lambda s,**k:vm.append(s) or ''),\
    patch.object(backend,'configure_upper',return_value={'exact_suffix_only':True}),patch.object(backend,'docker',side_effect=docker_call),\
    patch.object(backend,'capture_logs'),patch.object(backend,'git_trees',return_value={}),\
    patch.object(probe.scoped,'wait_cohort',return_value=identity('1')|{'running':True,'health':'healthy'}),\
    patch.object(verify,'state_snapshot',return_value=snapshot()),patch.object(runtime,'inspect',return_value={'Config':{'Env':['SVWAIT=60']},'HostConfig':{'RestartPolicy':{'Name':'no','MaximumRetryCount':0}}}):
     backend.boot(0)
   mounts=[s for s in vm if 'mount -t overlay' in s];self.assertEqual(len(mounts),3)
   for role in runtime.DESTS:self.assertTrue(any('lowerdir=/immutable/'+role+',' in s for s in mounts))
   runs=[r for r in docker if r[0]=='run'];self.assertEqual(len(runs),1);self.assertIn('--restart',runs[0]);self.assertIn('no',runs[0])
   self.assertEqual(runtime.WORLD,old_world);self.assertEqual(reset.VM_ROOT,old_vm)
 def test_colliding_namespace_is_never_claimed_or_deleted(self):
  doc=self.doc()|{'neutral_base':'http://127.0.0.1:8026'}
  with tempfile.TemporaryDirectory() as folder:
   backend=probe.NativeBackend(doc,Path(folder))
   with patch.object(backend,'container_exists',return_value=True),patch.object(backend,'docker') as docker,patch.object(backend,'vm') as vm:
    with self.assertRaises(ValueError):backend.boot(0)
    with self.assertRaises(ValueError):backend.teardown(0)
    docker.assert_not_called();vm.assert_not_called()
 def test_actual_teardown_targets_only_claimed_owned_namespace_and_unmounts_all(self):
  doc=self.doc()|{'neutral_base':'http://127.0.0.1:8026'}
  with tempfile.TemporaryDirectory() as folder:
   backend=probe.NativeBackend(doc,Path(folder));backend.owned_cycles.add(0);scripts=[];commands=[]
   def docker(*args,**kwargs):
    commands.append(args)
    return '{}' if args[0]=='inspect' else ''
   with patch.object(backend,'container_exists',side_effect=[True,False]),patch.object(backend,'docker',side_effect=docker),    patch.object(backend,'vm',side_effect=lambda script,**kw:scripts.append(script) or ''),patch.object(backend,'capture_logs'):
     result=backend.teardown(0)
   self.assertTrue(result['owned_vm_subtree_absent']);self.assertEqual(sum('umount ' in s for s in scripts),3)
   self.assertEqual([a for a in commands if a[0]=='stop'],[('stop','--time','300',doc['container_prefix']+'-0')])
   self.assertEqual([a for a in commands if a[0]=='rm'],[('rm',doc['container_prefix']+'-0')])
   deletes=[s for s in scripts if 'rm -rf' in s];self.assertEqual(len(deletes),1)
   self.assertIn(doc['vm_root']+'/cycle-0',deletes[0]);self.assertNotIn('/immutable/',deletes[0])
 def test_log_capture_failure_does_not_skip_owned_container_cleanup(self):
  doc=self.doc()|{'neutral_base':'http://127.0.0.1:8026'}
  with tempfile.TemporaryDirectory() as folder:
   backend=probe.NativeBackend(doc,Path(folder));backend.owned_cycles.add(0)
   with patch.object(backend,'container_exists',side_effect=[True,False]),patch.object(backend,'docker',return_value='{}') as docker,    patch.object(backend,'vm',return_value=''),patch.object(backend,'capture_logs',side_effect=RuntimeError('logs unavailable')):
     with self.assertRaises(RuntimeError):backend.teardown(0)
     self.assertIn(('rm',doc['container_prefix']+'-0'),[c.args for c in docker.call_args_list])
   self.assertTrue((Path(folder)/'cycle-0-teardown.private.json').exists())
 def test_container_absence_rejects_daemon_error(self):
  backend,root=self.run_fixture();backend=probe.NativeBackend(backend.doc,root)
  result=subprocess.CompletedProcess([],1,b'',b'Cannot connect to Docker daemon')
  with patch.object(subprocess,'run',return_value=result):
   with self.assertRaises(ValueError):backend.container_exists('owned','absence.private.json')
 def test_upper_edit_executes_exact_suffix_against_real_fixture_only(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);lower=root/'lower';lower.mkdir();upper=root/'clone/config/merged';upper.mkdir(parents=True)
   base=b"external_url 'http://localhost:8018'\npuma['worker_processes'] = 0\n"
   (lower/'gitlab.rb').write_bytes(base);(upper/'gitlab.rb').write_bytes(base)
   backend=probe.NativeBackend({'seed_lowerdirs':{'config':str(lower)}},root)
   def vm(script,**kwargs):
    body=script.split("\n",1)[1].rsplit('\nNEUTRAL_CONFIG',1)[0]
    return subprocess.run(['python3','-c',body],capture_output=True,check=True,text=True).stdout
   with patch.object(backend,'vm',side_effect=vm):result=backend.configure_upper(0,str(root/'clone'))
   self.assertEqual((lower/'gitlab.rb').read_bytes(),base);self.assertEqual((upper/'gitlab.rb').read_bytes(),base+probe.profile.SUFFIX.encode())
   self.assertTrue(result['exact_suffix_only'])
 def test_effective_ruby_reader_filters_secrets_and_requires_real_booleans(self):
  tree={'monitoring':{},'gitlab':{'secret':'do-not-emit'}}
  for setting in probe.profile.SETTINGS:
   section,field=probe.re.fullmatch(r"(\w+)\['(\w+)'\] = false",setting).groups()
   block='monitoring' if section in ['alertmanager','gitlab_exporter','node_exporter','postgres_exporter','prometheus','redis_exporter'] else 'gitlab'
   tree[block][section]={field:False}
  result=subprocess.run(['ruby','-e',probe.effective_reader_ruby()],input=json.dumps(tree),text=True,capture_output=True)
  self.assertEqual(result.returncode,0);self.assertEqual(json.loads(result.stdout),probe.EXPECTED_SETTINGS);self.assertNotIn('do-not-emit',result.stdout+result.stderr)
  tree['monitoring']['node_exporter']['enable']='false'
  bad=subprocess.run(['ruby','-e',probe.effective_reader_ruby()],input=json.dumps(tree),text=True,capture_output=True)
  self.assertNotEqual(bad.returncode,0);self.assertEqual(bad.stderr,'effective settings unavailable\n');self.assertEqual(bad.stdout,'')
 def test_env_has_only_telemetry_suffix_and_neutral_port_delta(self):
  env=b"SVWAIT=60\nGITLAB_OMNIBUS_CONFIG=external_url 'http://127.0.0.1:8018'; nginx['listen_port'] = 8018; puma['worker_processes'] = 0\nUNCHANGED=value\n"
  rendered=probe.render_environment(env,8026)
  self.assertIn(b"puma['worker_processes'] = 0",rendered);self.assertIn(b'UNCHANGED=value\n',rendered);self.assertIn(b'SVWAIT=60\n',rendered)
  self.assertEqual(rendered.count(b' = false'),9);self.assertEqual(rendered.count(b'8026'),2)
  for port in [8018,8100,False]:
   with self.assertRaises(ValueError):probe.render_environment(env,port)
 def audit_fixture(self):
  backend,root=self.run_fixture();plan=root/'plan.private.json';permit=root/'permit.private.json';doc=backend.doc
  probe.source.write_new(plan,doc)
  probe.source.write_new(permit,{'accepted':True,'plan_sha256':probe.source.sha(probe.source.private(plan)),'source_sha256s':doc['source_sha256s']})
  probe.source.write_new(root/'run-intent.private.json',{'plan_sha256':probe.source.sha(probe.source.private(plan)),
   'permit_sha256':probe.source.sha(probe.source.private(permit)),'worker_and_lease_proof':{'old_worker_processes':0,'supervisor_locks_exclusive':True}})
  result=probe.execute_cycles(doc,snapshot(),backend);result['raw_file_sha256s']=probe.raw_refs(root);probe.source.write_new(root/'result.private.json',result)
  return backend,root,plan,permit
 def test_saved_auditor_reopens_full_git_sql_lifecycle_and_logs(self):
  backend,root,plan,permit=self.audit_fixture()
  with patch.object(probe,'checked_plan',return_value=(backend.doc,{},snapshot())):result=probe.audit(plan=plan,permit=permit)
  self.assertEqual(result['neutral_cycles_verified'],3);self.assertEqual(result['control_credit'],0);self.assertGreater(result['raw_files_verified'],200)
 def test_saved_auditor_rejects_tampered_raw_bytes_and_semantically_forged_manifest(self):
  for forged in [False,True]:
   backend,root,plan,permit=self.audit_fixture();target=root/'cycle-1-effective.private.json'
   target.write_text(json.dumps(probe.EXPECTED_SETTINGS|{"node_exporter['enable']":True}))
   if forged:
    result=json.loads(probe.source.private(root/'result.private.json'));result['raw_file_sha256s']=probe.raw_refs(root)
    (root/'result.private.json').write_bytes(probe.factory.canonical(result))
   with patch.object(probe,'checked_plan',return_value=(backend.doc,{},snapshot())):
    with self.assertRaises(ValueError):probe.audit(plan=plan,permit=permit)
 def test_real_run_acquires_existing_leases_retains_failure_and_consumes_intent(self):
  backend,root=self.run_fixture(('boot',1));doc=backend.doc|{'evaluator_root':str(Path(probe.__file__).resolve().parents[1]),'epoch_root':str(root/'epoch')}
  backend.doc=doc
  for folder in ['controls','audit-only-continuation-controls-v1','post-reset-continuation-controls-v2']:
   path=root/'epoch'/folder;path.mkdir(parents=True);(path/'.supervisor.lock').touch()
  plan=root/'plan.private.json';permit=root/'permit.private.json';probe.source.write_new(plan,doc)
  probe.source.write_new(permit,{'schema':'envloop-gitlab-neutral-telemetry-root-permit-v1','accepted':True,'plan_path':str(plan),
   'plan_sha256':probe.source.sha(probe.source.private(plan)),'source_sha256s':doc['source_sha256s'],'cycles':3,'task_ids_consumed':0,'note':'reviewed'})
  def lease():
   for folder in ['controls','audit-only-continuation-controls-v1','post-reset-continuation-controls-v2']:
    fd=os.open(root/'epoch'/folder/'.supervisor.lock',os.O_WRONLY)
    try:
     with self.assertRaises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    finally:os.close(fd)
   return {'old_worker_processes':0,'supervisor_locks_exclusive':True}
  with patch.object(probe,'checked_plan',return_value=(doc,{},snapshot())),patch.object(backend,'lease_proof',side_effect=lease):
   with self.assertRaises(RuntimeError):probe.run(plan=plan,permit=permit,execute=True,backend_factory=lambda d,o:backend)
   self.assertTrue(backend.running);self.assertTrue((root/'failure.private.json').exists());self.assertFalse((root/'result.private.json').exists())
   failure=json.loads(probe.source.private(root/'failure.private.json'));self.assertEqual(failure['control_credit'],0)
   with self.assertRaises(ValueError):probe.run(plan=plan,permit=permit,execute=True,backend_factory=lambda d,o:backend)
  self.assertEqual([v for k,v in backend.calls if k=='boot'],[0,1])
 def test_one_use_intent_prevents_replay_before_native_calls(self):
  backend,root=self.run_fixture();doc=backend.doc|{'evaluator_root':str(Path(probe.__file__).resolve().parents[1])}
  plan=root/'plan.private.json';permit=root/'permit.private.json';probe.source.write_new(plan,doc)
  probe.source.write_new(permit,{'schema':'envloop-gitlab-neutral-telemetry-root-permit-v1','accepted':True,'plan_path':str(plan),
   'plan_sha256':probe.source.sha(probe.source.private(plan)),'source_sha256s':doc['source_sha256s'],'cycles':3,'task_ids_consumed':0,'note':'reviewed'})
  probe.source.write_new(root/'run-intent.private.json',{'one_use':True})
  with patch.object(probe,'checked_plan',return_value=(doc,{},snapshot())),patch.object(probe,'NativeBackend') as native:
   with self.assertRaises(ValueError):probe.run(plan=plan,permit=permit,execute=True,backend_factory=native)
   native.assert_not_called()

if __name__=='__main__':unittest.main()
