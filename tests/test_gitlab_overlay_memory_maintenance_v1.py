"""Overlay recovery never clears directories or starts before exact mounts."""
from __future__ import annotations
import copy
from pathlib import Path
from contextlib import nullcontext
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from gitlab_world import v066_overlay_memory_maintenance_v1 as m


def fixture(mounted=True):
 recipe={};readback={}
 for role in m.ROLES:
  base='/var/lib/envloop-gitlab-cow-v3/'+role
  paths={'lower':'/var/lib/docker/volumes/envloop-gitlab-world-v3-'+role+'/_data',
         'upper':base+'/upper','work':base+'/work','merged':base+'/merged'}
  recipe[role]=paths
  readback[role]={'paths':paths,'directories':{k:{'inode':i+1,'mode':0o755,'uid':0,'gid':0} for i,k in enumerate(paths)},
    'mount':{'fstype':'overlay','mount_options':['rw','relatime'],'options':[
     'lowerdir='+paths['lower'],'upperdir='+paths['upper'],'workdir='+paths['work']]} if mounted else None}
 return recipe,readback


class OverlayMaintenanceTests(unittest.TestCase):
 def test_exact_three_overlay_options_are_required(self):
  recipe,before=fixture();self.assertTrue(m.verify_mounts(recipe,before))
  for alteration in ('filesystem','lower','upper','readonly'):
   changed=copy.deepcopy(before)
   if alteration=='filesystem':changed['data']['mount']['fstype']='ext4'
   elif alteration=='readonly':changed['data']['mount']['mount_options']=['ro']
   else:changed['data']['mount']['options'][0 if alteration=='lower' else 1]=alteration+'dir=/wrong'
   with self.assertRaises(ValueError):m.verify_mounts(recipe,changed)

 def test_missing_mount_is_remounted_using_same_existing_dirs_only(self):
  recipe,after=fixture();_recipe,unmounted=fixture(False)
  with patch.object(m,'vm_readback',side_effect=[unmounted,after]),patch.object(m.reset,'vm_shell',return_value='') as shell:
   m.remount_existing(recipe,after)
  self.assertEqual(shell.call_count,3)
  for call in shell.call_args_list:
   text=call.args[0];self.assertTrue(text.startswith('mount -t overlay'))
   for forbidden in ('mkdir','rm ','umount','cp ','reset'):self.assertNotIn(forbidden,text)

 def test_changed_upper_or_work_inode_refuses_remount(self):
  recipe,before=fixture();_recipe,unmounted=fixture(False)
  for directory in ('upper','work','lower'):
   changed=copy.deepcopy(unmounted);changed['data']['directories'][directory]['inode']=999
   with patch.object(m,'vm_readback',return_value=changed),patch.object(m.reset,'vm_shell',side_effect=AssertionError('No mount allowed')):
    with self.assertRaisesRegex(ValueError,'directory identity'):m.remount_existing(recipe,before)

 def test_existing_wrong_mount_never_unmounted_or_replaced(self):
  recipe,before=fixture();changed=copy.deepcopy(before);changed['config']['mount']['options'][0]='lowerdir=/wrong'
  with patch.object(m,'vm_readback',return_value=changed),patch.object(m.reset,'vm_shell',side_effect=AssertionError('No mutation allowed')):
   with self.assertRaisesRegex(ValueError,'unexpected mount'):m.remount_existing(recipe,before)

 def test_execute_disabled_before_source_read_or_any_command(self):
  with patch.object(m,'validate',side_effect=AssertionError('No source read')):
   with self.assertRaisesRegex(ValueError,'execution flag'):m.execute(plan_path=Path('/absent'),output_root=Path('/absent'))

 def test_wrong_postboot_mount_prevents_original_container_start(self):
  with TemporaryDirectory() as d:
   root=Path(d);plan=root/'plan.json';m.source.write_new(plan,{})
   recipe,readback=fixture();evaluator=Path(m.__file__).resolve().parents[1]
   value={'evaluator_root':str(evaluator),'original31_snapshot':{'baseline':'exact'},'original_container_id':'exact-original-id',
          'overlay_recipe':recipe,'before_overlay_readback':readback,'resize_argv':['offline-colima-start'],
          'original_seed_volume_identities':{'preserved':True}}
   stopped={'Id':'exact-original-id','State':{'Running':False,'ExitCode':0}};commands=[]
   with patch.object(m,'validate',return_value=value),patch.object(m,'original_scope',side_effect=lambda _:nullcontext()),\
        patch.object(m,'worker_proof',return_value={}),patch.object(m.verify,'state_snapshot',return_value={'baseline':'exact'}),\
        patch.object(m.runtime,'inspect',return_value=stopped),patch.object(m,'vm_readback',return_value=readback),\
        patch.object(m.runtime,'docker',side_effect=lambda *a,**k:commands.append(a)),patch.object(m.subprocess,'run'),\
        patch.object(m,'seed_identities',return_value={'preserved':True}),patch.object(m,'remount_existing',side_effect=ValueError('Wrong mount')):
    result=m.execute(plan_path=plan,output_root=root/'operation',execute_reviewed=True)
   self.assertIn('failure',result['status']);self.assertEqual(commands,[('stop','--time','300','exact-original-id')])


if __name__=='__main__':unittest.main()
