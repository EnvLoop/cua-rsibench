from types import SimpleNamespace
import unittest
from native_desktop_factory.native_accessibility_branch_diagnostic_v26 import branches,MAX_CHILDREN
from tests.test_native_desktop_accessibility_probe_v23 import Node,API

class DiagnosticTests(unittest.TestCase):
 def test_oversized_native_branch_is_recorded_before_rejection_without_child_enumeration(self):
  class Virtual(Node):
   @property
   def childCount(self):return 16777216
   def __getitem__(self,index):raise AssertionError('Virtual cells must not be enumerated')
  table=Virtual('table',['visible','showing','enabled'],[0,100,1280,700]);window=Node('frame',['visible','showing'],[0,0,1280,800],[table]);result=branches(API,window,native_uid=1000,native_pid=42)
  self.assertEqual(result['records'][1]['child_count'],16777216);self.assertEqual(result['cap_rejections'][0]['reason'],'existing_child_count_cap');self.assertFalse(result['safe_target_metadata_produced']);self.assertTrue(result['original_caps_unchanged'])
 def test_optional_interface_errors_do_not_erase_actual_oversized_branch(self):
  class Virtual(Node):
   @property
   def childCount(self):return 16777216
  class Unsupported:
   def get_table_iface(self):raise NotImplementedError()
   def get_collection_iface(self):raise RuntimeError()
  table=Virtual('table',['visible','showing'],[0,100,1280,700]);table.value=Unsupported();window=Node('frame',['visible','showing'],[0,0,1280,800],[table]);result=branches(API,window,native_uid=1000,native_pid=42)
  record=result['records'][1];self.assertEqual(record['table_interface_error_class'],'NotImplementedError');self.assertEqual(record['collection_interface_error_class'],'RuntimeError');self.assertEqual(record['child_count'],16777216);self.assertEqual(result['cap_rejections'][0]['child_count'],16777216)
 def test_hidden_branch_records_states_without_reading_names_or_values(self):
  text=Node('text',[],[0,0,1,1]);window=Node('frame',['visible','showing'],[0,0,1280,800],[text]);result=branches(API,window,native_uid=1000,native_pid=42)
  self.assertEqual(result['records'][1]['not_traversed'],'not_showing_visible');self.assertFalse(result['partial_tree_qualified']);self.assertNotIn('name',result['records'][1])
 def test_record_bound_is_explicit_and_never_qualifies_partial_tree(self):
  window=Node('frame',['visible','showing'],[0,0,1280,800],[Node('text',['visible','showing'],[0,0,10,10])]);result=branches(API,window,native_uid=1000,native_pid=42,limit=1)
  self.assertEqual(result['record_count'],1);self.assertEqual(result['cap_rejections'][0]['reason'],'diagnostic_record_bound');self.assertFalse(result['partial_tree_qualified'])

if __name__=='__main__':unittest.main()
