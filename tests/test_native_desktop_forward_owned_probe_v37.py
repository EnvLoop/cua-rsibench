import unittest
from native_desktop_factory.native_forward_owned_probe_v37 import ForwardOwnedPaths

class Node:
 def __init__(self,key,pid=100):self.key=key;self.pid=pid;self.children=[];self.parent=None;self.index=0;self.count_override=None
 def add(self,node):node.index=len(self.children);node.parent=self;self.children.append(node);return node
 def get_process_id(self):return self.pid
 def get_child_count(self):return len(self.children) if self.count_override is None else self.count_override
 def get_child_at_index(self,index):return self.children[index]
 def get_index_in_parent(self):return self.index
 def get_parent(self):return self.parent
def identity(node):return {'available':True,'identity_sha256':node.key}
class ForwardTests(unittest.TestCase):
 def world(self):
  root=Node('owned');a=root.add(Node('panel1'));b=a.add(Node('panel2'));pane=b.add(Node('pane'));pane.parent=Node('orphan-frame');leaf=pane.add(Node('leaf'));return root,a,b,pane,leaf
 def test_actual_forward_path_repairs_reverse_parent_mismatch_without_pid_guess(self):
  root,a,b,pane,leaf=self.world();r=ForwardOwnedPaths(root,100,identity)
  self.assertEqual([n.key for n in r.ancestors(leaf,root)],['leaf','pane','panel2','panel1','owned'])
  self.assertEqual([e['child_index'] for e in r.proofs[-1]['actual_forward_edges_reopened']],[0,0,0])
 def test_same_pid_unreachable_frame_and_cycle_refused(self):
  root,*_=self.world();r=ForwardOwnedPaths(root,100,identity)
  with self.assertRaises(ValueError):r.ancestors(Node('foreign-same-pid'),root)
  cycle=Node('cycle');cycle.parent=cycle
  with self.assertRaisesRegex(ValueError,'cycle'):r.ancestors(cycle,root)
 def test_current_edge_change_or_index_mismatch_refuses(self):
  for mutation in ('edge','index'):
   root,a,b,pane,leaf=self.world();r=ForwardOwnedPaths(root,100,identity)
   if mutation=='edge':b.children[0]=Node('new-pane')
   else:pane.index=4
   with self.assertRaises(ValueError):r.ancestors(leaf,root)
 def test_large_virtual_collection_deferred_and_foreign_process_refused(self):
  root=Node('owned');root.count_override=2**31;r=ForwardOwnedPaths(root,100,identity);self.assertEqual(r.deferred[0]['actual_child_count'],2**31)
  with self.assertRaises(ValueError):r.ancestors(Node('unseen'),root)
  root=Node('owned');root.add(Node('foreign',200))
  with self.assertRaisesRegex(ValueError,'process'):ForwardOwnedPaths(root,100,identity)
 def test_exact_native_identity_across_wrappers_reopens_current_forward_nodes(self):
  root,*_,pane,leaf=self.world();r=ForwardOwnedPaths(root,100,identity);copy=Node('pane');self.assertEqual(r.ancestors(copy,root)[0].key,pane.key)
if __name__=='__main__':unittest.main()
