"""Offline source/clone/32-project/no-replay tests; no Docker or model calls."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from gitlab_world import factory,verify,runtime,bootstrap,reset
from gitlab_world import v066_prospective_cohort_v5 as source
from gitlab_world import v066_prospective_cohort_runtime_v5 as scoped
from gitlab_world import v066_prospective_cohort_controller_v5 as control


def seal(snapshot):
 snapshot.pop('business_sha256',None);snapshot['business_sha256']=source.sha(factory.canonical(snapshot));return snapshot


def snapshot(count):
 ids=list(range(1,count+1));db={name:[] for name in ['groups','group_members','operators','projects','issues','issue_assignees','labels','issue_label_links','milestones','members','merge_requests']}
 db['groups']=[{'id':i,'visibility_level':0} for i in [1,2,3]]
 db['operators']=[{'id':100+i,'admin':False} for i in [1,2,3]]
 db['group_members']=[{'id':i,'user_id':100+i,'source_id':i,'access_level':50} for i in [1,2,3]]+[
  {'id':10+i,'user_id':1,'source_id':i,'access_level':50} for i in [1,2,3]]
 for i in ids:
  db['projects'].append({'id':i})
  db['issues'] += [{'id':10*i+j,'project_id':i} for j in range(6)]
  db['members'] += [{'id':10*i+j,'source_id':i} for j in range(3)]
  db['merge_requests'] += [{'id':10*i+j,'target_project_id':i} for j in range(2)]
  db['labels'].append({'id':i,'project_id':i,'title':'pristine'})
 git={str(i):{'refs':{'refs/heads/main':'a'*40,'refs/heads/a':'b'*40,'refs/heads/b':'c'*40},'main_blobs_sha256':{}} for i in ids}
 return seal({'schema':verify.SCHEMA,'project_ids':ids,'db':db,'git':git})


def roster():
 rows=[];retired=[]
 for i in range(100):
  reserved=10<=i<15;family=20 if reserved else i//5
  row={'task_id':('reserve-' if reserved else 'original-')+str(i),'source_family_sha256':source.sha(str(family).encode()),
       'template_group':'workflow-'+str(i%5),'package_sha256':None if reserved else source.sha(('old-'+str(i)).encode()),
       'provenance':'first_precommitted_fifo_reserve_family' if reserved else 'original_roster'}
  rows.append(row)
  if reserved:retired.append({**row,'task_id':'original-'+str(i),'source_family_sha256':source.sha(b'2')})
 return rows,retired


class CohortTests(unittest.TestCase):
 def test_no_bootstrap_or_task_execution_without_explicit_gate(self):
  with patch.object(runtime,'docker',side_effect=AssertionError('No Docker call allowed')):
   with self.assertRaisesRegex(ValueError,'explicit'):scoped.bootstrap_clone(freeze_path=Path('/absent'),permit_path=None)
   with self.assertRaisesRegex(ValueError,'disabled'):control.run(freeze_path=Path('/absent'),permit_path=Path('/absent'))
   with self.assertRaisesRegex(ValueError,'root source acceptance'):control.review(freeze_path=Path('/absent'),review_path=Path('/absent'),permit_path=Path('/absent'),phase='bootstrap')

 def test_metadata_world_discards_all_task_answers_and_prompts(self):
  project={k:[] if k=='advisories' else {} if k=='principals' else 'metadata' for k in source.PROJECT_METADATA_KEYS}
  task={k:'metadata' for k in source.TASK_METADATA_KEYS};task.update(prompt='sealed prompt',oracle={'expected_answer':'sealed answer'},gold='sealed gold')
  world={'schema':factory.SCHEMA,'world_seed_sha256':'a'*64,'projects':[project],'reserve_projects':[], 'tasks':[task],'reserve_tasks':[]}
  metadata=source.metadata_world(json.dumps(world).encode())
  self.assertEqual(set(metadata['tasks'][0]),set(source.TASK_METADATA_KEYS))
  self.assertNotIn('sealed',json.dumps(metadata))

 def test_whole_family_fifo_roster_rejects_partial_swap_retired_id_and_family_leak(self):
  rows,retired=roster();self.assertEqual(source.validate_roster(rows,retired)['source_families'],20)
  changed=copy.deepcopy(rows);changed[10]['provenance']='original_roster'
  with self.assertRaises(ValueError):source.validate_roster(changed,retired)
  changed=copy.deepcopy(rows);changed[10]['task_id']=retired[0]['task_id']
  with self.assertRaises(ValueError):source.validate_roster(changed,retired)
  changed=copy.deepcopy(rows);changed[10]['source_family_sha256']=rows[0]['source_family_sha256']
  with self.assertRaises(ValueError):source.validate_roster(changed,retired)

 def test_32_project_snapshot_counts_and_nonadmin_acl_are_exact(self):
  baseline=snapshot(32);self.assertEqual(scoped.validate_snapshot(baseline,32)['project_count'],32)
  for corruption in ['members','acl','digest']:
   changed=copy.deepcopy(baseline)
   if corruption=='members':changed['db']['members'].pop();seal(changed)
   elif corruption=='acl':changed['db']['operators'][0]['admin']=True;seal(changed)
   else:changed['business_sha256']='f'*64
   with self.assertRaises(ValueError):scoped.validate_snapshot(changed,32)

 def test_original31_project_projection_detects_bootstrap_collateral_change(self):
  before=snapshot(31);after=snapshot(32)
  self.assertEqual(scoped.original_projection(after,before),before)
  after['db']['labels'][0]['title']='collateral edit';seal(after)
  self.assertNotEqual(scoped.original_projection(after,before),before)

 def test_new_port_guard_rejects_original_world_and_external_urls(self):
  self.assertTrue(scoped.local_url('http://127.0.0.1:8016/project'))
  for url in ['http://127.0.0.1:8014/project','https://example.com','http://user:password@localhost:8016']:
   self.assertFalse(scoped.local_url(url))

 def test_uncertain_and_failed_journals_never_replay_or_skip(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);(root/'controls').mkdir();rows=[]
   control.append(root,rows,{'kind':'intent','task_index':0})
   self.assertIsNotNone(control.journal_state(rows)['pending'])
   with self.assertRaises(ValueError):control.append(root,rows,{'kind':'intent','task_index':0})
  with TemporaryDirectory() as directory:
   root=Path(directory);(root/'controls').mkdir();rows=[]
   control.append(root,rows,{'kind':'intent','task_index':0});control.append(root,rows,{'kind':'terminal','task_index':0,'passed':False})
   self.assertTrue(control.journal_state(rows)['terminal_failure'])
   with self.assertRaises(ValueError):control.append(root,rows,{'kind':'intent','task_index':1})

 def test_all100_packages_rebind_baseline_acl_and_keep_old_passes_historical(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);rows,retired=roster();tasks=[]
   for row in rows:
    tasks.append({'task_id':row['task_id'],'template_group':row['template_group'],'source_family':str(20 if row['provenance']!='original_roster' else int(row['task_id'].split('-')[-1])//5)})
   world={'tasks':tasks,'reserve_tasks':[]};source.write_new(root/'world-private.json',world)
   source.write_new(root/'baseline-persisted-state.json',snapshot(32));freeze=root/'freeze.json';source.write_new(freeze,{'source':'sealed'})
   value={'epoch_root':str(root),'candidate_roster':rows,'retired_task_metadata':retired,'source_sha256s':{}}
   first=control.freeze_baseline_plan(value=value,freeze_path=freeze,baseline=snapshot(32),acl_sha='a'*64,world=world)
   plan=json.loads((root/'cohort-plan.private.json').read_bytes())
   self.assertEqual(first['candidate_count'],100);self.assertEqual(plan['historical_controls_transferred'],0)
   self.assertTrue(all(row['historical_control_transferred'] is False for row in plan['task_roster']))
   self.assertTrue(all(row['package_sha256']!=row['previous_package_sha256'] for row in plan['task_roster']))

 def test_readonly_prefix_before_bootstrap_does_not_touch_app(self):
  with TemporaryDirectory() as directory:
   value={'epoch_root':str(Path(directory)/'absent')}
   with patch.object(source,'validate_source',return_value=value),patch.object(runtime,'docker',side_effect=AssertionError('No Docker call')):
    audit=control.audit_prefix(freeze_path=Path('/metadata'))
   self.assertEqual(audit['new_baseline_controls_completed'],0)
   self.assertEqual(audit['historical_controls_transferred'],0)

 def test_cohort_context_restores_original_module_globals_without_docker(self):
  from contextlib import nullcontext
  with TemporaryDirectory() as directory:
   original_private=runtime.PRIVATE;original_world=runtime.WORLD;original_progress=bootstrap.PROGRESS_FILE
   value={'epoch_root':directory,'clone_container_name':'envloop-gitlab-prospective-abc123def456',
          'clone_volume_names':{r:'new-'+r for r in ['config','logs','data']},'clone_vm_root':'/new-private-vm'}
   with patch.object(scoped,'private_screenshots',side_effect=lambda _:nullcontext()),patch.object(runtime,'docker',side_effect=AssertionError('No Docker call')):
    with scoped.cohort_context(value):
     self.assertEqual(runtime.BASE,'http://127.0.0.1:8016');self.assertEqual(bootstrap.PROGRESS_FILE,Path(directory)/'bootstrap-progress.json')
    self.assertEqual(runtime.PRIVATE,original_private);self.assertEqual(runtime.WORLD,original_world);self.assertEqual(bootstrap.PROGRESS_FILE,original_progress)

 def test_bootstrap_permit_cannot_dispatch_controls_or_change_source(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);freeze=root/'freeze.json';source.write_new(freeze,{'closed':'source'})
   value={'epoch_root':str(root/'new-epoch'),'source_sha256s':{'source.py':'a'*64}}
   reviewed=root/'review.json';permit=root/'permit.json'
   with patch.object(source,'validate_source',return_value=value),patch.object(runtime,'docker',side_effect=AssertionError('No Docker')):
    control.review(freeze_path=freeze,review_path=reviewed,permit_path=permit,phase='bootstrap',root_review_accepted=True,note='Offline source test only')
   control.checked_permit(freeze_path=freeze,permit_path=permit,value=value,phase='bootstrap')
   with self.assertRaises(ValueError):control.checked_permit(freeze_path=freeze,permit_path=permit,value=value,phase='controls')
   changed={**value,'source_sha256s':{'source.py':'b'*64}}
   with self.assertRaises(ValueError):control.checked_permit(freeze_path=freeze,permit_path=permit,value=changed,phase='bootstrap')

 def test_control_permit_is_impossible_before_new_baseline_acl_exists(self):
  with TemporaryDirectory() as directory:
   root=Path(directory);epoch=root/'epoch';epoch.mkdir();freeze=root/'freeze.json';source.write_new(freeze,{'closed':'source'})
   value={'epoch_root':str(epoch),'source_sha256s':{}}
   with patch.object(source,'validate_source',return_value=value),patch.object(runtime,'docker',side_effect=AssertionError('No Docker')):
    with self.assertRaises(ValueError):
     control.review(freeze_path=freeze,review_path=root/'review',permit_path=root/'permit',phase='controls',root_review_accepted=True,note='No baseline')
   self.assertFalse((root/'permit').exists())

 def test_bootstrap_uses_new_volumes_readonly_source_and_never_stops_original(self):
  from contextlib import nullcontext
  with TemporaryDirectory() as directory:
   base=Path(directory);original=base/'original';original.mkdir(mode=0o700);epoch=base/'epoch'
   progress={'projects':{'p'+str(i):{'project_id':i,'complete':True} for i in range(1,32)},'groups':{},'users':{}}
   for name,data in [('bootstrap-progress.json',progress),('operator-bootstrap-private.json',{}),('operator-credentials-private.json',{}),('world-private.json',{'tasks':[],'reserve_projects':[],'reserve_tasks':[]}),('baseline-persisted-state.json',snapshot(31))]:source.write_new(original/name,data)
   for name,text in [('world-seed.txt','offline-seed'),('runtime.env',"GITLAB_OMNIBUS_CONFIG=external_url 'http://127.0.0.1:8014'; nginx['listen_port'] = 8014\n")]:
    path=original/name;path.write_text(text);path.chmod(0o600)
   recipe=base/'recipe.json';source.write_new(recipe,{'project':{'full_path':'new-project'},'task_metadata':[]})
   freeze=base/'freeze.json';permit=base/'permit.json';source.write_new(freeze,{});source.write_new(permit,{})
   tag='envloop-gitlab-prospective-abc123def456';value={'evaluator_root':str(Path(scoped.__file__).resolve().parents[1]),'original_private_root':str(original),'epoch_root':str(epoch),
    'recipe_path':str(recipe),'clone_container_name':tag,'clone_volume_names':{r:tag+'-'+r for r in ['config','logs','data']},
    'clone_vm_root':'/var/lib/'+tag,'original_seed_lowerdirs':{r:'/var/lib/docker/volumes/original-'+r+'/_data' for r in ['config','logs','data']}}
   calls=[];scripts=[];seeded=[]
   def docker(*args,**kwargs):
    calls.append(args)
    if args[:2]==('volume','inspect'):raise subprocess.CalledProcessError(1,args)
    return 'offline'
   def seed_one(_api,project,_progress):seeded.append(project['full_path'])
   with patch.object(source,'validate_source',return_value=value),patch.object(control,'checked_permit',return_value={}),patch.object(control,'freeze_baseline_plan',return_value={'plan_sha256':'a'*64}),patch.object(runtime,'proof',return_value={'identity':'original-unchanged'}),patch.object(runtime,'docker',side_effect=docker),patch.object(reset,'vm_shell',side_effect=lambda script,**kw:scripts.append(script)),patch.object(scoped,'cohort_context',side_effect=lambda _:nullcontext()),patch.object(scoped,'wait_cohort',return_value={}),patch.object(factory,'_tasks',return_value=[]),patch.object(bootstrap,'api_token',return_value='offline-not-a-credential'),patch.object(bootstrap,'_seed_one',side_effect=seed_one),patch.object(verify,'state_snapshot',side_effect=[snapshot(31),snapshot(32),snapshot(32)]),patch.object(scoped,'native_acl',return_value={'own_project_successes':3,'cross_partition_denials':6}),patch.object(reset,'freeze',return_value={'same_business_sha256':True}):
    result=scoped.bootstrap_clone(freeze_path=freeze,permit_path=permit,execute=True)
   self.assertEqual(result['status'],'new32_project_fifo_baseline_acl_exact_cold_clone_frozen')
   self.assertEqual(seeded,['new-project'])
   self.assertTrue(all('mount -o remount,bind,ro' in script for script in scripts[:3]))
   self.assertFalse(any(args[0] in ['stop','rm'] for args in calls))
   run_command=next(args for args in calls if args[0]=='run')
   self.assertIn('127.0.0.1:8016:8016',run_command)
   self.assertEqual(json.loads(source.private(original/'bootstrap-progress.json')),progress)


if __name__=='__main__':unittest.main()
