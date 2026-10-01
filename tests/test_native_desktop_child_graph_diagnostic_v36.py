import unittest
from native_desktop_factory.native_child_graph_diagnostic_v36 import capture

class Node:
 def __init__(self,key,children=(),count=None):self.key=key;self.children=list(children);self.count=count;self.queried=[]
 def get_role_name(self):return 'root pane'
 def get_process_id(self):return 100
 def get_child_count(self):return len(self.children) if self.count is None else self.count
 def get_child_at_index(self,index):self.queried.append(index);return self.children[index]
def identity(node):return {'available':True,'identity_sha256':node.key}
class GraphTests(unittest.TestCase):
 def test_exact_forward_edge_survives_missing_reverse_parent_without_authorizing(self):
  child=Node('actual');root=Node('owned',[child]);value=capture(root,{'actual','foreign'},identity=identity)
  path=value['exact_forward_paths_to_requested_identities']['actual'][0]
  self.assertEqual(path[0]['parent_identity_sha256'],'owned');self.assertEqual(path[0]['native_child_index'],0);self.assertEqual(path[0]['returned_child_identity']['identity_sha256'],'actual')
  self.assertEqual(value['exact_forward_paths_to_requested_identities']['foreign'],[]);self.assertFalse(value['native_ownership_authorized'])
 def test_large_virtual_descendants_not_enumerated(self):
  root=Node('owned',count=2**31);value=capture(root,{'target'},identity=identity)
  self.assertEqual(root.queried,[]);self.assertEqual(value['deferred'][0]['actual_child_count'],2**31);self.assertFalse(value['complete_tree_claimed'])
 def test_cycles_and_budget_stop_do_not_invent_missing_membership(self):
  root=Node('owned');root.children=[root,Node('other')];value=capture(root,{'absent'},identity=identity,limit=2)
  self.assertLessEqual(len(value['nodes']),2);self.assertEqual(value['exact_forward_paths_to_requested_identities']['absent'],[])
 def test_depth_bound_and_missing_child_record_uncertainty(self):
  root=Node('owned',[None]);value=capture(root,{'absent'},identity=identity)
  self.assertEqual(value['deferred'][0]['reason'],'child_query_unavailable')
  root=Node('owned',[Node('deep')]);value=capture(root,{'deep'},identity=identity,max_depth=0)
  self.assertEqual(root.queried,[]);self.assertEqual(value['exact_forward_paths_to_requested_identities']['deep'],[])
if __name__=='__main__':unittest.main()
