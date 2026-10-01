"""Offline native-call-path fixtures, never native qualification."""
from types import SimpleNamespace
import unittest
from native_desktop_factory import native_visible_surface_probe_v30 as reader

API=SimpleNamespace(CoordType=SimpleNamespace(SCREEN='screen'),StateType=SimpleNamespace(**{n:n for n in ['VISIBLE','SHOWING','FOCUSED','ENABLED','SENSITIVE','EDITABLE','MANAGES_DESCENDANTS','DEFUNCT','STALE']}))
class Node:
 def __init__(self,role='panel',*,flags=None,box=(0,0,400,300),pid=100):
  self.role=role;self.flags=set(flags or ['VISIBLE','SHOWING','ENABLED','SENSITIVE']);self.box=box;self.pid=pid;self.parent=None;self.children=[];self.hit=None;self.child_reads=0;self.index=0;self.forbid_children=False
 def add(self,node):node.parent=self;node.index=len(self.children);self.children.append(node);return node
 def get_process_id(self):return self.pid
 def get_state_set(self):return SimpleNamespace(contains=lambda key:key in self.flags)
 def get_role_name(self):return self.role
 def get_parent(self):return self.parent
 def get_index_in_parent(self):return self.index
 def get_name(self):raise AssertionError('Fixture document values must not be queried')
 def get_component_iface(self):return SimpleNamespace(get_extents=lambda coord:SimpleNamespace(x=self.box[0],y=self.box[1],width=self.box[2],height=self.box[3]),get_accessible_at_point=lambda x,y,coord:self.hit)
 def get_child_count(self):
  self.child_reads+=1
  if self.forbid_children:raise AssertionError('Hidden/managed child count must not be queried')
  return len(self.children)
 def get_child_at_index(self,index):self.child_reads+=1;return self.children[index]
 def get_collection_iface(self):raise AssertionError('Recursive Collection must not be called')

def ancestry(node,window):
 result=[]
 for _ in range(32):
  if node is None:raise ValueError('foreign native ancestry')
  result.append(node)
  if node is window:return result
  node=node.parent
 raise ValueError('unbounded native ancestry')

class VisibleTests(unittest.TestCase):
 def surface(self,window):return reader.bounded_surface(API,window,pid=100,uid=1000,viewport=[400,300],ancestry=ancestry)
 def test_hidden_and_offscreen_branches_are_pruned_before_child_enumeration(self):
  window=Node('frame');hidden=window.add(Node('menu',flags=['VISIBLE'],box=(-100,0,40,20)));hidden.forbid_children=True
  offscreen=window.add(Node(box=(-100,0,40,20)));offscreen.forbid_children=True
  targets,facts,branches,focus=self.surface(window)
  self.assertEqual([b.get('pruned') for b in branches[1:]],['native_hidden','native_offscreen']);self.assertEqual(hidden.child_reads,0);self.assertEqual(offscreen.child_reads,0);self.assertIsNone(focus)
 def test_managed_and_large_native_children_are_explicitly_deferred(self):
  window=Node('frame');table=window.add(Node('table',flags=['VISIBLE','SHOWING','ENABLED','SENSITIVE','MANAGES_DESCENDANTS']));table.forbid_children=True
  targets,facts,branches,focus=self.surface(window)
  self.assertTrue(branches[1]['deferred']);self.assertEqual(table.child_reads,0);self.assertFalse(targets[1]['keyboard']);self.assertIsNone(focus)
  table.flags.remove('MANAGES_DESCENDANTS');table.get_child_count=lambda:1000000
  self.assertEqual(self.surface(window)[2][1]['reason'],'native_child_count_cap')
 def test_lazy_physical_hit_descends_only_native_point_path_and_rejects_foreign(self):
  window=Node('frame');panel=window.add(Node());cell=panel.add(Node('table cell',flags=['VISIBLE','SHOWING','ENABLED','SENSITIVE','EDITABLE','FOCUSED']));window.hit=panel;panel.hit=cell
  hit,depth=reader.physical_hit(API,window,[40,40],pid=100,viewport=[400,300],ancestry=ancestry)
  self.assertIs(hit,cell);self.assertEqual(depth,3);self.assertTrue(all(n.child_reads==0 for n in [window,panel,cell]))
  cell.pid=200
  with self.assertRaisesRegex(ValueError,'ownership'):reader.physical_hit(API,window,[40,40],pid=100,viewport=[400,300],ancestry=ancestry)
 def test_selected_is_not_focus_and_actual_disabled_native_leaf_stays_disabled(self):
  window=Node('frame');cell=window.add(Node('table cell',flags=['VISIBLE','SHOWING','SELECTED','EDITABLE']));window.hit=cell
  targets,facts,branches,focus=self.surface(window)
  self.assertIsNone(focus);self.assertFalse(targets[1]['enabled']);self.assertFalse(targets[1]['keyboard']);self.assertFalse(facts[1]['native_flags']['FOCUSED'])
  cell.flags.update(['ENABLED','SENSITIVE','FOCUSED'])
  self.assertEqual(self.surface(window)[3][0]['ref'],targets[1]['ref'])
 def test_hit_cycle_unknown_stale_and_node_limit_fail_without_partial_admission(self):
  window=Node('frame');child=window.add(Node());window.hit=child;child.hit=window
  with self.assertRaisesRegex(ValueError,'cycle'):reader.physical_hit(API,window,[40,40],pid=100,viewport=[400,300],ancestry=ancestry)
  child.hit=None;child.flags.add('STALE')
  with self.assertRaisesRegex(ValueError,'unsafe'):reader.physical_hit(API,window,[40,40],pid=100,viewport=[400,300],ancestry=ancestry)

if __name__=='__main__':unittest.main()
