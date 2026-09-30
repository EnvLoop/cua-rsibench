"""Independent review guards: resources, raw ACL evidence and one-shot child."""
from __future__ import annotations
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PIL import Image
from gitlab_world import runtime,reset,verify,operators
from gitlab_world import v066_prospective_cohort_v5 as source
from gitlab_world import v066_prospective_cohort_runtime_v5 as scoped
from gitlab_world import v066_prospective_cohort_controller_v5 as controller
from gitlab_world import v066_prospective_resource_preflight_v5 as resource
from tests.test_gitlab_prospective_cohort_v5 import snapshot


class ReviewGuardsTests(unittest.TestCase):
 def test_original_six_gib_vm_is_rejected_before_any_vm_shell_or_snapshot(self):
  with patch.object(runtime,'docker',return_value=json.dumps({'MemTotal':6*1024**3,'NCPU':3})),\
       patch.object(reset,'vm_shell',side_effect=AssertionError('Memory refusal must precede VM shell')),\
       patch.object(verify,'state_snapshot',side_effect=AssertionError('Memory refusal must precede business readback')):
   with self.assertRaisesRegex(ValueError,'at least10GiB'):resource.preflight({})

 def test_12_gib_readonly_disk_and_exact_baseline_proof(self):
  with TemporaryDirectory() as d:
   root=Path(d);baseline=snapshot(31);source.write_new(root/'baseline-persisted-state.json',baseline)
   lower={r:'/var/lib/docker/volumes/old-'+r+'/_data' for r in ('config','logs','data')}
   text=str(12*1024**3)+'\n'+'\n'.join('1000\t'+lower[r] for r in ('config','logs','data'))
   with patch.object(runtime,'docker',return_value=json.dumps({'MemTotal':12*1024**3,'NCPU':3})),\
        patch.object(reset,'vm_shell',return_value=text) as shell,\
        patch.object(runtime,'proof',return_value={'running':True,'health':'healthy','image_id':runtime.IMAGE_ID}),\
        patch.object(verify,'state_snapshot',return_value=baseline):
    result=resource.preflight({'original_seed_lowerdirs':lower,'original_private_root':str(root)})
   self.assertEqual(result['original_seed_copy_bytes'],3000)
   self.assertTrue(result['original31_exact_readback'])
   script=shell.call_args.args[0]
   self.assertNotIn('mount',script);self.assertNotIn('rm ',script);self.assertNotIn('cp ',script)

 def test_insufficient_disk_refuses_old_app_and_sql_probe(self):
  lower={r:'/var/lib/docker/volumes/old-'+r+'/_data' for r in ('config','logs','data')}
  text='100\n'+'\n'.join('1000\t'+lower[r] for r in ('config','logs','data'))
  with patch.object(runtime,'docker',return_value=json.dumps({'MemTotal':12*1024**3,'NCPU':3})),patch.object(reset,'vm_shell',return_value=text),\
       patch.object(runtime,'proof',side_effect=AssertionError('Disk refusal must precede app readback')):
   with self.assertRaisesRegex(ValueError,'disk lacks'):resource.preflight({'original_seed_lowerdirs':lower})

 def test_resource_refusal_leaves_bootstrap_epoch_unconsumed(self):
  with TemporaryDirectory() as d:
   root=Path(d);epoch=root/'new-epoch';freeze=root/'freeze.json';permit=root/'permit.json'
   source.write_new(freeze,{});source.write_new(permit,{})
   value={'epoch_root':str(epoch),'original_private_root':str(root/'old'),
          'evaluator_root':str(Path(scoped.__file__).resolve().parents[1])}
   with patch.object(source,'validate_source',return_value=value),patch.object(controller,'checked_permit'),\
        patch.object(resource,'preflight',side_effect=ValueError('undersized VM')):
    with self.assertRaisesRegex(ValueError,'undersized'):scoped.bootstrap_clone(freeze_path=freeze,permit_path=permit,execute=True)
   self.assertFalse(epoch.exists())

 def acl_fixture(self,root):
  credentials={p:{'username':'fixture-'+p} for p in operators.PARTITIONS}
  source.write_new(root/'operator-credentials-private.json',credentials)
  image=Image.new('RGB',(1440,1000),'white');out=BytesIO();image.save(out,'PNG');raw=out.getvalue()
  cases=[]
  for p in operators.PARTITIONS:
   access={}
   for target in operators.PARTITIONS:
    path=root/'native-acl'/p/(target+'.png');path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    path.write_bytes(raw);path.chmod(0o600);own=p==target
    access[target]={'allowed_expected':own,'native_http_status':200 if own else 404,'project_title_visible':own,'screenshot_sha256':source.sha(raw)}
   cases.append({'partition':p,'fresh_browser_context':True,'user_sha256':source.factory.sha256(credentials[p]['username']),'access':access})
  return {'schema':'envloop-gitlab-prospective32-native-acl-private-v5','operator_count':3,'own_project_successes':3,'cross_partition_denials':6,
          'new_fifo_project_in_final_operator_probe':True,'non_admin_actors':True,'cases':cases}

 def test_aggregate_acl_labels_alone_cannot_authorize_controls(self):
  with TemporaryDirectory() as d:
   root=Path(d);acl=self.acl_fixture(root);acl.pop('cases')
   with self.assertRaisesRegex(ValueError,'actual browser'):scoped.audit_native_acl(root,acl)

 def test_all_nine_acl_pngs_and_browser_principals_are_reopened(self):
  with TemporaryDirectory() as d:
   root=Path(d);acl=self.acl_fixture(root)
   self.assertEqual(scoped.audit_native_acl(root,acl)['native_acl_pngs_reopened'],9)
   target=root/'native-acl'/operators.PARTITIONS[0]/(operators.PARTITIONS[1]+'.png');target.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'screenshot bytes'):scoped.audit_native_acl(root,acl)

 def test_rejected_journal_append_retains_original_valid_bytes(self):
  with TemporaryDirectory() as d:
   root=Path(d);(root/'controls').mkdir(mode=0o700);rows=[]
   controller.append(root,rows,{'kind':'intent','task_index':0});before=source.private(root/'controls/journal.private.jsonl')
   with self.assertRaises(ValueError):controller.append(root,rows,{'kind':'intent','task_index':0})
   self.assertEqual(source.private(root/'controls/journal.private.jsonl'),before)
   self.assertEqual(len(rows),1)

 def test_cold_seed_binding_keeps_generation_mutable_but_rejects_original_volumes(self):
  with TemporaryDirectory() as d:
   root=Path(d);baseline=snapshot(32);volumes={r:'new-'+r for r in ('config','logs','data')}
   value={'epoch_root':str(root),'clone_volume_names':volumes}
   state={'schema':'envloop-gitlab-overlay-cold-reset-v1','baseline_business_sha256':baseline['business_sha256'],
          'seed_volume_lowerdirs':{r:'/var/lib/docker/volumes/'+n+'/_data' for r,n in volumes.items()},
          'clone_generation':1,'first_clone_container_id_sha256':'a'*64,'first_clone_readback_equal':True}
   source.write_new(root/'cow-reset-state.json',state);first=controller.cold_seed_binding(value,baseline)
   state['clone_generation']=4;source.persist(root/'cow-reset-state.json',state)
   self.assertEqual(controller.cold_seed_binding(value,baseline),first)
   state['seed_volume_lowerdirs']['data']='/var/lib/docker/volumes/original-data/_data';source.persist(root/'cow-reset-state.json',state)
   with self.assertRaisesRegex(ValueError,'dedicated new volumes'):controller.cold_seed_binding(value,baseline)

 def test_second_child_invocation_refuses_before_gui_or_state_readback(self):
  with TemporaryDirectory() as d:
   root=Path(d);folder=root/'controls/supervision';folder.mkdir(parents=True,mode=0o700)
   freeze=root/'freeze.json';permit=root/'permit.json';source.write_new(freeze,{});source.write_new(permit,{})
   pending={'task_index':0,'supervisor_pid':123,'entry_sha256':'a'*64}
   value={'evaluator_root':str(Path(controller.__file__).resolve().parents[1]),'epoch_root':str(root)}
   with patch.object(source,'validate_source',return_value=value),patch.object(controller,'checked_permit',return_value={'first_index':0,'maximum_control_count':1}),\
        patch.object(controller,'baseline_inputs',return_value=({},'b'*64,{})),patch.object(controller,'read_journal',return_value=[]),\
        patch.object(controller,'journal_state',return_value={'pending':pending}),patch.object(controller.os,'getppid',return_value=123),\
        patch.object(scoped,'cohort_context',side_effect=RuntimeError('stop after first durable child marker')) as context:
    with self.assertRaisesRegex(RuntimeError,'durable child marker'):controller.child(freeze_path=freeze,permit_path=permit,index=0,parent_pid=123)
    self.assertTrue((folder/'000-child-started.private.json').exists())
    with self.assertRaises(FileExistsError):controller.child(freeze_path=freeze,permit_path=permit,index=0,parent_pid=123)
    self.assertEqual(context.call_count,1)


if __name__=='__main__':unittest.main()
