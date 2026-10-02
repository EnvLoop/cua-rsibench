"""Meaningful offline successor gates; no Docker/application/provider calls."""
import copy,json,os,subprocess,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import nullcontext
from unittest.mock import patch
from gitlab_world import factory,runtime,verify,reset,bootstrap
from gitlab_world import v066_prospective_cohort_v6 as source
from gitlab_world import v066_prospective_cohort_runtime_v6 as scoped
from gitlab_world import v066_prospective_cohort_controller_v6 as control
from tests.test_gitlab_prospective_cohort_v5 import snapshot,seal,roster
PROFILE={'SVWAIT':'60','readiness_seconds':900,'supervisor_seconds':7200,'startup_restart_attempts':0}

def rows_v6():
 rows,retired=roster();family={'tasks':[{'task_id':'next-'+str(i),'template_group':'workflow-'+str(i),'source_family':'next-source','partition':'final_candidate_unsealed'} for i in range(5)]}
 new,second=source.replacement_roster(rows,family)
 return new,retired+second

class SuccessorGates(unittest.TestCase):
 def test_complete_next_family_balanced100_no_old_ids(self):
  rows,retired=rows_v6();self.assertEqual(source.validate_roster(rows,retired)['tasks'],100)
  self.assertEqual({r['source_family_sha256'] for r in rows[:5]},{factory.sha256('next-source')})
  for mutation in ['partial','retired','collision']:
   bad=copy.deepcopy(rows)
   if mutation=='partial':bad[0]['provenance']='original_roster'
   elif mutation=='retired':bad[0]['task_id']=retired[-1]['task_id']
   else:bad[0]['source_family_sha256']=bad[5]['source_family_sha256']
   with self.assertRaises(ValueError):source.validate_roster(bad,retired)
 def test_no_overlap_or_partial_fifo_generator(self):
  rows,_=roster();t={'task_id':rows[0]['task_id'],'template_group':'workflow-0','source_family':'new','partition':'final_candidate_unsealed'}
  with self.assertRaises(ValueError):source.replacement_roster(rows,{'tasks':[t]})
 def test_33_project_counts_acl_digest_and_old32_projection(self):
  before=snapshot(32);after=snapshot(33)
  self.assertEqual(scoped.validate_snapshot(after,33)['project_count'],33)
  self.assertEqual(scoped.original_projection(after,before),before)
  altered=copy.deepcopy(after);altered['db']['labels'][0]['title']='collateral';seal(altered)
  self.assertNotEqual(scoped.original_projection(altered,before),before)
  for key in ['members','operators']:
   bad=copy.deepcopy(after);bad['db'][key].pop();seal(bad)
   with self.assertRaises(ValueError):scoped.validate_snapshot(bad,33)
 def test_profile_exactly_once_and_unknown_prior_setting_refused(self):
  env='OTHER=unchanged\n';value=scoped.profile_environment(env)
  self.assertEqual(value,'OTHER=unchanged\nSVWAIT=60\n')
  self.assertEqual(scoped.profile_environment(value),value)
  for bad in ['SVWAIT=7\n','SVWAIT=60\nSVWAIT=60\n']:
   with self.assertRaises(ValueError):scoped.profile_environment(bad)
 def test_runtime_profile_file_and_metadata_bound(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);p=root/'runtime.env';p.write_text('SVWAIT=60\n');p.chmod(0o600)
   binding=scoped.profile_binding(root,{'startup_profile':PROFILE});self.assertEqual(binding['runtime_env_sha256'],source.sha(p.read_bytes()))
   p.write_text('SVWAIT=61\n')
   with self.assertRaises(ValueError):scoped.profile_binding(root,{'startup_profile':PROFILE})
 def test_actual_env_image_health_http_all_required(self):
  state={'Image':runtime.IMAGE_ID,'Config':{'Env':['SVWAIT=60']},'State':{'Running':True,'Health':{'Status':'healthy'}}}
  with patch.object(runtime,'inspect',return_value=state),patch.object(runtime,'_http_ready',return_value=True),patch.object(runtime,'proof',return_value={'exact':'proof'}):
   self.assertEqual(scoped.wait_cohort(),{'exact':'proof'})
  for env in [[],['SVWAIT=7'],['SVWAIT=60','SVWAIT=60']]:
   with patch.object(runtime,'inspect',return_value={**state,'Config':{'Env':env}}):
    with self.assertRaises(ValueError):scoped.wait_cohort()
  with patch.object(runtime,'inspect',return_value={**state,'State':{'Running':False}}):
   with self.assertRaises(RuntimeError):scoped.wait_cohort()
 def test_terminal_and_uncertain_journal_never_replay_advance(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);(root/'controls').mkdir();rows=[]
   control.append(root,rows,{'kind':'intent','task_index':0})
   with self.assertRaises(ValueError):control.append(root,rows,{'kind':'intent','task_index':0})
   control.append(root,rows,{'kind':'terminal','task_index':0,'passed':False})
   with self.assertRaises(ValueError):control.append(root,rows,{'kind':'intent','task_index':1})
 def test_successor_port_rejects_both_original_and_parent(self):
  self.assertTrue(scoped.local_url('http://127.0.0.1:8018/project'))
  for url in ['http://127.0.0.1:8014/project','http://127.0.0.1:8016/project','https://example.com','http://u:p@localhost:8018']:
   self.assertFalse(scoped.local_url(url))
 def test_source_preparation_cannot_dispatch_before_root_gate(self):
  with patch.object(runtime,'docker',side_effect=AssertionError('Forbidden live call')):
   with self.assertRaisesRegex(ValueError,'explicit'):scoped.bootstrap_clone(freeze_path=Path('/missing'),permit_path=None)
   with self.assertRaisesRegex(ValueError,'disabled'):control.run(freeze_path=Path('/missing'),permit_path=Path('/missing'))
 def test_context_restores_originals_and_child_reset_carries_epoch_env_once(self):
  with TemporaryDirectory() as directory:
   root=Path(directory)
   env=root/'runtime.env';env.write_text('SVWAIT=60\n');env.chmod(0o600)
   value={'epoch_root':str(root),'clone_container_name':'successor-fixture','clone_volume_names':{r:'new-'+r for r in ['config','logs','data']},'clone_vm_root':'/new','startup_profile':PROFILE}
   original=(runtime.PRIVATE,runtime.WORLD,reset._create_case);calls=[]
   with patch.object(scoped,'private_screenshots',return_value=nullcontext()),patch.object(runtime,'docker',side_effect=lambda *a,**k:calls.append(a)),patch.object(scoped,'wait_cohort',return_value={'ready':True}):
    with scoped.cohort_context(value):
     self.assertEqual(reset._create_case(),{'ready':True});self.assertEqual(runtime.BASE,'http://127.0.0.1:8018')
   self.assertEqual((runtime.PRIVATE,runtime.WORLD,reset._create_case),original)
   self.assertEqual(len(calls),1);self.assertEqual(calls[0][calls[0].index('--env-file')+1],str(env))
 def test_all100_package_plan_binds_new_profile_and_baseline(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);rows,retired=rows_v6();tasks=[]
   for row in rows:
    oldid=int(row['task_id'].split('-')[-1]);family='next-source' if oldid<5 and row['provenance']=='second_precommitted_fifo_reserve_family' else str(20 if row['provenance']=='first_precommitted_fifo_reserve_family' else oldid//5)
    tasks.append({'task_id':row['task_id'],'template_group':row['template_group'],'source_family':family})
   world={'tasks':tasks,'reserve_tasks':[]};source.write_new(root/'world-private.json',world);source.write_new(root/'baseline-persisted-state.json',snapshot(33))
   freeze=root/'freeze';source.write_new(freeze,{})
   env=root/'runtime.env';env.write_text('SVWAIT=60\n');env.chmod(0o600)
   value={'epoch_root':str(root),'candidate_roster':rows,'retired_task_metadata':retired,'source_sha256s':{},'clone_volume_names':{r:'fixture-'+r for r in ['config','logs','data']},'startup_profile':PROFILE}
   source.write_new(root/'cow-reset-state.json',{'schema':'envloop-gitlab-overlay-cold-reset-v1','baseline_business_sha256':snapshot(33)['business_sha256'],'seed_volume_lowerdirs':{r:'/var/lib/docker/volumes/fixture-'+r+'/_data' for r in ['config','logs','data']},'clone_generation':1,'first_clone_readback_equal':True,'first_clone_container_id_sha256':'a'*64})
   control.freeze_baseline_plan(value=value,freeze_path=freeze,baseline=snapshot(33),acl_sha='a'*64,world=world)
   plan=json.loads((root/'cohort-plan.private.json').read_bytes())
   self.assertEqual(plan['startup_profile_binding']['runtime_env_sha256'],source.sha(env.read_bytes()))
   self.assertEqual(plan['historical_controls_transferred'],0)
   self.assertTrue(all(r['historical_control_transferred'] is False for r in plan['task_roster']))
   self.assertEqual(len({r['package_sha256'] for r in plan['task_roster']}),100)
 def test_graceful_archive_targets_only_terminal_parent_exact_identity(self):
  from gitlab_world import v066_prospective_cohort_runtime_v5 as parent_scoped
  from gitlab_world import v066_prospective_cohort_v5 as parent_source
  with TemporaryDirectory() as directory:
   root=Path(directory);source.write_new(root/'baseline-persisted-state.json',snapshot(32))
   parent={'epoch_root':str(root),'clone_container_name':'terminal-parent','clone_volume_names':{r:'parent-'+r for r in ['config','logs','data']},'clone_vm_root':'/parent'}
   before={'container_id_sha256':'a'*64,'image_ref':runtime.IMAGE,'image_id':runtime.IMAGE_ID,'mounts':{},'ports':{},'running':True,'health':'healthy'}
   after={**before,'running':False};calls=[]
   with patch.object(scoped,'no_old_worker',return_value={}),patch.object(parent_source,'validate_source',return_value=parent),patch.object(parent_scoped,'private_screenshots',return_value=nullcontext()),patch.object(runtime,'proof',side_effect=[before,after]),patch.object(runtime,'docker',side_effect=lambda *a,**k:calls.append(a)),patch.object(verify,'state_snapshot',return_value=snapshot(32)):
    result=scoped.archive_parent({'evaluator_root':'/evaluator','parent_source_freeze_path':'/closed'},{'parent_runtime_proof':before})
   self.assertTrue(result['parent_explicitly_stopped']);self.assertEqual(calls,[('stop','--time','300','terminal-parent')])
   self.assertNotEqual(runtime.WORLD,'terminal-parent')
 def test_bootstrap_readonly_copy_parent_archival_then_one_new_runtime(self):
  with TemporaryDirectory() as directory:
   base=Path(directory);original=base/'parent';original.mkdir(mode=0o700);epoch=base/'successor'
   progress={'projects':{'p'+str(i):{'project_id':i,'complete':True} for i in range(1,33)},'groups':{},'users':{}}
   for name,data in [('bootstrap-progress.json',progress),('operator-bootstrap-private.json',{}),('operator-credentials-private.json',{}),('world-private.json',{'tasks':[],'reserve_projects':[],'reserve_tasks':[]}),('baseline-persisted-state.json',snapshot(32))]:source.write_new(original/name,data)
   for name,text in [('world-seed.txt','offline-seed'),('runtime.env',"GITLAB_OMNIBUS_CONFIG=external_url 'http://127.0.0.1:8016'; nginx['listen_port'] = 8016\n")]:
    p=original/name;p.write_text(text);p.chmod(0o600)
   recipe=base/'recipe';source.write_new(recipe,{'project':{'full_path':'next-project'},'task_metadata':[]})
   freeze=base/'freeze';permit=base/'permit';source.write_new(freeze,{});source.write_new(permit,{})
   tag='envloop-gitlab-successor-abc123def456';value={'evaluator_root':str(Path(scoped.__file__).resolve().parents[1]),'original_private_root':str(original),'epoch_root':str(epoch),'startup_profile':PROFILE,'recipe_path':str(recipe),'clone_container_name':tag,'clone_volume_names':{r:tag+'-'+r for r in ['config','logs','data']},'clone_vm_root':'/var/lib/'+tag,'original_seed_lowerdirs':{r:'/var/lib/docker/volumes/parent-'+r+'/_data' for r in ['config','logs','data']}}
   calls=[];scripts=[];order=[]
   def docker(*args,**kwargs):
    calls.append(args)
    if args[:2]==('volume','inspect'):raise subprocess.CalledProcessError(1,args)
    if args[0]=='run':order.append('start-successor')
    return 'offline'
   def archive(*args):order.append('stop-parent');return {'parent_explicitly_stopped':True,'parent_seed_and_terminal_files_unchanged':True}
   with patch.object(scoped,'resource_preflight',return_value={'readonly':True}),patch.object(source,'validate_source',return_value=value),patch.object(control,'checked_permit',return_value={}),patch.object(control,'freeze_baseline_plan',return_value={'plan_sha256':'a'*64}),patch.object(scoped,'archive_parent',side_effect=archive),patch.object(runtime,'proof',return_value={'identity':'protected-original'}),patch.object(runtime,'docker',side_effect=docker),patch.object(reset,'vm_shell',side_effect=lambda script,**k:scripts.append(script)),patch.object(scoped,'cohort_context',return_value=nullcontext()),patch.object(scoped,'wait_cohort',return_value={}),patch.object(factory,'_tasks',return_value=[]),patch.object(bootstrap,'api_token',return_value='offline'),patch.object(bootstrap,'_seed_one',return_value=None),patch.object(verify,'state_snapshot',side_effect=[snapshot(32),snapshot(33),snapshot(33)]),patch.object(scoped,'native_acl',return_value={'own_project_successes':3,'cross_partition_denials':6}),patch.object(reset,'freeze',return_value={'same_business_sha256':True}):
    result=scoped.bootstrap_clone(freeze_path=freeze,permit_path=permit,execute=True)
   self.assertEqual(result['status'],'new33_project_fifo_baseline_acl_exact_cold_clone_frozen')
   self.assertEqual(order,['stop-parent','start-successor'])
   self.assertEqual([a[2] for a in calls if a[:2]==('volume','create')],list(value['clone_volume_names'].values()))
   self.assertEqual(sum('mount -o remount,bind,ro' in script for script in scripts),3)
   self.assertFalse(any(a[0] in ['stop','rm'] for a in calls))
   self.assertIn('SVWAIT=60',source.private(epoch/'runtime.env').decode())
   receipt=json.loads(source.private(epoch/'bootstrap-receipt.private.json'))
   self.assertEqual(receipt['startup_profile_binding']['runtime_env_sha256'],source.sha(source.private(epoch/'runtime.env')))
 def test_concurrent_old_worker_refused_without_app_call(self):
  fake=f'999999 1 python -m gitlab_world.v066_prospective_cohort_controller_v5 run\n{os.getpid()} 1 python current\n'
  with patch.object(subprocess,'run',return_value=type('Result',(),{'stdout':fake})()):
   with self.assertRaisesRegex(ValueError,'Concurrent'):scoped.no_old_worker(Path('/evaluator'))

if __name__=='__main__':unittest.main()
