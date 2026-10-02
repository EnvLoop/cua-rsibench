"""Point certainty and ancestor state fixtures; no native qualification."""
import unittest
from tests.test_native_desktop_visible_surface_probe_v30 import Node,API,ancestry
from native_desktop_factory import native_visible_surface_probe_v31 as reader

class PointTests(unittest.TestCase):
 def hit(self,node):return reader.physical_hit(API,node,[40,40],pid=100,viewport=[400,300],ancestry=ancestry)
 def test_root_none_is_unknown_and_never_an_enabled_window_canvas(self):
  with self.assertRaisesRegex(ValueError,'root point'):self.hit(Node('frame'))
 def test_virtual_and_large_table_none_refused_without_child_enumeration(self):
  window=Node('frame');table=window.add(Node('table',flags=['VISIBLE','SHOWING','ENABLED','SENSITIVE','MANAGES_DESCENDANTS']));window.hit=table;table.forbid_children=True
  with self.assertRaisesRegex(ValueError,'deferred point'):self.hit(window)
  self.assertEqual(table.child_reads,0);table.flags.remove('MANAGES_DESCENDANTS');table.get_child_count=lambda:1000000
  with self.assertRaisesRegex(ValueError,'proved leaf'):self.hit(window)
 def test_actual_leaf_after_native_parent_hit_is_accepted(self):
  window=Node('frame');leaf=window.add(Node('table cell',flags=['VISIBLE','SHOWING','ENABLED','SENSITIVE','EDITABLE','FOCUSED']));window.hit=leaf
  self.assertEqual(self.hit(window),(leaf,2));target,fact=reader.native_record(API,leaf,window,pid=100,uid=1000,viewport=[400,300],ancestry=ancestry)
  self.assertTrue(target['enabled']);self.assertTrue(target['keyboard']);self.assertTrue(fact['ancestor_states_checked'])
 def test_disabled_ancestor_cannot_enable_leaf(self):
  window=Node('frame');panel=window.add(Node(flags=['VISIBLE','SHOWING']));leaf=panel.add(Node('table cell',flags=['VISIBLE','SHOWING','ENABLED','SENSITIVE','EDITABLE','FOCUSED']));window.hit=panel;panel.hit=leaf
  target,fact=reader.native_record(API,leaf,window,pid=100,uid=1000,viewport=[400,300],ancestry=ancestry)
  self.assertFalse(target['enabled']);self.assertFalse(target['keyboard']);self.assertFalse(fact['ancestor_native_flags'][1]['ENABLED'])


class PrivateDiagnosticTests(unittest.TestCase):
 def test_nested_actual_point_failure_keeps_first_stage_and_private_error_only(self):
  import tempfile,json
  from pathlib import Path
  window=Node('frame')
  def runner(**kwargs):return {'native_result':reader.namespace['physical_hit'](API,window,[40,40],pid=100,viewport=[400,300],ancestry=ancestry)}
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'private.json';result=reader.diagnostic_run(filename='fixture.xlsx',viewport=[400,300],runner=runner,error_path=path)
   self.assertEqual(result['first_failed_stage'],'physical_hit');self.assertNotIn('Native root point hit unavailable',json.dumps(result));self.assertEqual(path.stat().st_mode&0o777,0o600)
   raw=json.loads(path.read_bytes());self.assertEqual(raw['errors'][0]['raw_error_string'],'Native root point hit unavailable');self.assertFalse(raw['actor_access_authorized'])

if __name__=='__main__':unittest.main()
