from types import SimpleNamespace
import unittest
from native_desktop_factory import native_window_inventory_diagnostic_v34 as inventory
from native_desktop_factory import native_hit_identity_diagnostic_v33 as identities
from tests.test_native_desktop_hit_identity_diagnostic_v33 import Node

class InventoryTests(unittest.TestCase):
 def test_actual_client_list_and_absolute_geometry_parse_without_guesses(self):
  self.assertEqual(inventory.client_ids('_NET_CLIENT_LIST(WINDOW): window id # 0x100, 0x200'),[256,512])
  text='Absolute upper-left X: 2\nAbsolute upper-left Y: 85\nWidth: 579\nHeight: 316\nRelative upper-left X: 0\nRelative upper-left Y: 25\n'
  self.assertEqual(inventory.x_geometry(text),[2,85,579,316])
  for value in ['_NET_CLIENT_LIST: not found','_NET_CLIENT_LIST(WINDOW): window id # 0x100, 0x100','_NET_CLIENT_LIST(WINDOW): window id # 0x0']:
   with self.assertRaises(ValueError):inventory.client_ids(value)
 def test_client_count_and_geometry_ambiguity_refuse_instead_of_truncating(self):
  with self.assertRaisesRegex(ValueError,'count'):inventory.client_ids('_NET_CLIENT_LIST(WINDOW): window id # '+','.join(hex(n) for n in range(1,66)))
  with self.assertRaisesRegex(ValueError,'ambiguous'):inventory.x_geometry('Absolute upper-left X: 0\nAbsolute upper-left X: 1\nAbsolute upper-left Y: 27\nWidth: 1280\nHeight: 773\n')
 def test_exact_tuple_matches_one_physical_window_and_rejects_same_pid_only(self):
  windows=[{'xid':1,'pid':100,'uid':1000,'exe_sha256':'a'*64,'map_state':'IsViewable','title_sha256':'b'*64,'geometry':[0,27,1280,773]}]
  frames=[{'identity':{'identity_sha256':'c'*64},'native_pid':100,'native_states':{'VISIBLE':True,'SHOWING':True,'DEFUNCT':False,'STALE':False},'title_sha256':'b'*64,'geometry':[0,27,1280,773]},{'identity':{'identity_sha256':'d'*64},'native_pid':100,'native_states':{'VISIBLE':True,'SHOWING':True,'DEFUNCT':False,'STALE':False},'title_sha256':'b'*64,'geometry':[0,27,1280,748]}]
  result=inventory.exact_candidates(frames,windows,owned_pid=100,owned_uid=1000,owned_exe_sha256='a'*64)
  self.assertEqual(result[0]['status'],'unique_exact_metadata_candidate');self.assertEqual(result[0]['exact_metadata_candidate_xids'],[1]);self.assertEqual(result[1]['status'],'no_exact_candidate');self.assertFalse(result[0]['native_ownership_authorized']);self.assertFalse(result[1]['same_pid_shortcut_used'])
 def test_ambiguous_title_geometry_or_wrong_uid_exe_does_not_pick_a_window(self):
  frame={'identity':{'identity_sha256':'c'*64},'native_pid':100,'native_states':{'VISIBLE':True,'SHOWING':True,'DEFUNCT':False,'STALE':False},'title_sha256':'b'*64,'geometry':[0,27,1280,773]};window={'xid':1,'pid':100,'uid':1000,'exe_sha256':'a'*64,'map_state':'IsViewable','title_sha256':'b'*64,'geometry':frame['geometry']}
  result=inventory.exact_candidates([frame],[window,{**window,'xid':2}],owned_pid=100,owned_uid=1000,owned_exe_sha256='a'*64)[0];self.assertEqual(result['status'],'ambiguous_exact_metadata_candidates');self.assertEqual(result['exact_metadata_candidate_xids'],[1,2])
  for changed in [{**window,'uid':1001},{**window,'exe_sha256':'f'*64},{**window,'title_sha256':'f'*64}]:self.assertEqual(inventory.exact_candidates([frame],[changed],owned_pid=100,owned_uid=1000,owned_exe_sha256='a'*64)[0]['status'],'no_exact_candidate')
 def test_frame_title_hash_and_documented_attribute_map_are_retained_without_xid_inference(self):
  node=Node('/org/a11y/atspi/accessible/10',role='frame');node.get_name=lambda:'Synthetic frame title';node.get_attributes=lambda:{'window-id':'999','toolkit':'gtk'};node.get_state_set=lambda:SimpleNamespace(contains=lambda state:state in ['ACTIVE','VISIBLE','SHOWING'])
  api=SimpleNamespace(CoordType=SimpleNamespace(SCREEN='screen'),StateType=SimpleNamespace(**{n:n for n in ['ACTIVE','VISIBLE','SHOWING','DEFUNCT','STALE','MODAL']}))
  row=inventory.frame_facts(node,node,api,structural=identities.structural_facts,source='application_top_level');self.assertEqual(row['title_sha256'],inventory.sha(b'Synthetic frame title'));self.assertEqual(len(row['native_attributes']),2);self.assertNotIn('999',str(row));self.assertNotIn('Synthetic frame title',str(row));self.assertNotIn('xid',row);self.assertTrue(row['native_states']['ACTIVE'])
 def test_readonly_command_unknown_stderr_and_nonzero_exit_are_rejected(self):
  for exit_code,stderr in [(1,''),(0,'unknown diagnostic error')]:
   with self.assertRaises(ValueError):inventory.command(['xprop','-root','_NET_CLIENT_LIST'],runner=lambda *args,**kwargs:SimpleNamespace(returncode=exit_code,stdout='data',stderr=stderr))

 def test_physical_window_reopens_actual_proc_uid_executable_and_query_geometry(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);proc=root/'proc'/'100';proc.mkdir(parents=True);exe=root/'synthetic-executable';exe.write_bytes(b'synthetic native executable');(proc/'exe').symlink_to(exe);(proc/'status').write_text('Uid:\t1000\t1000\t1000\t1000\n')
   def query(args):
    if args[1]=='getwindowpid':return '100'
    if args[1]=='getwindowname':return 'Synthetic window title'
    if args[0]=='xwininfo':return 'Absolute upper-left X: 0\nAbsolute upper-left Y: 27\nWidth: 1280\nHeight: 773\nMap State: IsViewable\n'
    return 'WM_CLASS(STRING) = "libreoffice", "libreoffice-calc"'
   row=inventory.physical_window(256,query=query,proc_root=root/'proc');self.assertEqual(row['pid'],100);self.assertEqual(row['uid'],1000);self.assertEqual(row['exe_sha256'],inventory.sha(exe.read_bytes()));self.assertEqual(row['geometry'],[0,27,1280,773]);self.assertEqual(row['map_state'],'IsViewable');self.assertEqual(row['field_errors'],{})
 def test_nonshowing_native_geometry_and_unmapped_x11_do_not_get_exact_candidates(self):
  states={'VISIBLE':True,'SHOWING':True,'DEFUNCT':False,'STALE':False};frame={'identity':{'identity_sha256':'c'*64},'native_pid':100,'native_states':states,'title_sha256':'b'*64,'geometry':[0,27,1280,773]};window={'xid':1,'pid':100,'uid':1000,'exe_sha256':'a'*64,'title_sha256':'b'*64,'geometry':frame['geometry'],'map_state':'IsViewable'}
  frame['native_states']={**states,'SHOWING':False};self.assertEqual(inventory.exact_candidates([frame],[window],owned_pid=100,owned_uid=1000,owned_exe_sha256='a'*64)[0]['status'],'no_exact_candidate')
  frame['native_states']=states;window['map_state']='IsUnMapped';self.assertEqual(inventory.exact_candidates([frame],[window],owned_pid=100,owned_uid=1000,owned_exe_sha256='a'*64)[0]['status'],'no_exact_candidate')

if __name__=='__main__':unittest.main()
