import unittest
from types import SimpleNamespace
from native_desktop_factory import native_visible_surface_probe_v31 as original
from native_desktop_factory.native_terminal_hit_diagnostic_v38 import instrument
from tests.test_native_desktop_visible_surface_probe_v30 import Node,API,ancestry

class Writer:
 def __init__(self):self.rows=[]
 def append(self,row):self.rows.append(row.copy())
class TerminalTests(unittest.TestCase):
 def test_nonleaf_native_self_hit_is_recorded_and_original_refusal_preserved(self):
  window=Node('frame');panel=window.add(Node('panel'));panel.add(Node('text'));window.hit=panel;panel.hit=panel;writer=Writer()
  peer=SimpleNamespace(physical_hit=original.physical_hit,native_record=original.native_record,bounded_surface=original.bounded_surface,state_flags=original.state_flags,namespace=dict(original.namespace))
  module=instrument(peer,lambda node:{'identity_sha256':str(id(node))},writer)
  with self.assertRaisesRegex(ValueError,'not a proved leaf'):module.physical_hit(API,window,[40,40],pid=100,viewport=[400,300],ancestry=ancestry)
  facts=writer.rows[0];self.assertEqual(facts['native_child_count_already_returned'],1);self.assertEqual(facts['returned_hit_kind'],'same_native_object');self.assertEqual(facts['physical_point'],[40,40])
  self.assertTrue(any(r['kind']=='actual_native_terminal_child' for r in writer.rows))
 def test_valid_native_leaf_remains_accepted_without_failure_journal(self):
  window=Node('frame');leaf=window.add(Node('table cell'));window.hit=leaf;writer=Writer()
  peer=SimpleNamespace(physical_hit=original.physical_hit,native_record=original.native_record,bounded_surface=original.bounded_surface,state_flags=original.state_flags,namespace=dict(original.namespace));module=instrument(peer,lambda node:{'identity_sha256':str(id(node))},writer)
  self.assertIs(module.physical_hit(API,window,[40,40],pid=100,viewport=[400,300],ancestry=ancestry)[0],leaf);self.assertEqual(writer.rows,[])
if __name__=='__main__':unittest.main()

class StructuralRuntimeTests(unittest.TestCase):
 def test_menu_and_toolbar_children_are_inventory_only(self):
  from native_desktop_factory.native_terminal_hit_diagnostic_v38 import structural_record
  for role,count in [('menu',32),('tool bar',8),('unrecognized structural native role',1)]:
   window=Node('frame');container=window.add(Node(role,box=(0,51,400,25)))
   for _ in range(count):container.add(Node('menu item',box=(0,51,10,25)))
   record,facts=structural_record(original,API,container,window,pid=100,uid=1000,viewport=[400,300],ancestry=ancestry)
   self.assertFalse(record['enabled']);self.assertEqual(record['actions'],[]);self.assertEqual(facts['actual_native_child_count'],count)
 def test_actual_nonleaf_menu_blank_area_is_nonactionable_inventory_not_a_hit_waiver(self):
  from native_desktop_factory.native_terminal_hit_diagnostic_v38 import structural_record
  window=Node('frame');menu=window.add(Node('menu bar',box=(0,51,400,25)))
  for _ in range(11):menu.add(Node('menu item',box=(0,51,10,25)))
  menu.hit=None
  record,facts=structural_record(original,API,menu,window,pid=100,uid=1000,viewport=[400,300],ancestry=ancestry)
  self.assertFalse(record['enabled']);self.assertFalse(record['keyboard']);self.assertTrue(record['obscured']);self.assertEqual(record['actions'],[])
  self.assertTrue(facts['structural_inventory_only']);self.assertFalse(facts['point_hit_ownership_checked'])
  window.hit=menu
  with self.assertRaisesRegex(ValueError,'not a proved leaf'):original.physical_hit(API,window,[200,63],pid=100,viewport=[400,300],ancestry=ancestry)
 def test_foreign_parent_and_stale_structural_node_are_never_admitted(self):
  from native_desktop_factory.native_terminal_hit_diagnostic_v38 import structural_record
  for defect in ('pid','stale'):
   window=Node('frame');menu=window.add(Node('menu bar',box=(0,51,400,25)))
   if defect=='pid':menu.pid=200
   else:menu.flags.add('STALE')
   with self.assertRaises(ValueError):structural_record(original,API,menu,window,pid=100,uid=1000,viewport=[400,300],ancestry=ancestry)

class ExactForwardRuntimeTests(unittest.TestCase):
 def resolver(self):
  from native_desktop_factory import native_forward_owned_probe_v37 as peer
  from native_desktop_factory.native_terminal_hit_diagnostic_v38 import forward_owned_paths
  from tests.test_native_desktop_forward_owned_probe_v37 import Node as ForwardNode,identity
  writer=Writer();root=ForwardNode('root');child=root.add(ForwardNode('actual-child'));child.parent=ForwardNode('actual-different-reverse-parent');child.index=-1
  resolver=forward_owned_paths(peer,writer)(root,100,identity)
  return resolver,root,child,ForwardNode,writer
 def test_actual_minus_one_reverse_parent_mismatch_requires_twice_reopened_exact_slot(self):
  resolver,root,child,_,writer=self.resolver()
  self.assertEqual(resolver.ancestors(child,root),[child,root])
  proof=resolver.proofs[-1]['reverse_parent_inconsistencies'][0]
  self.assertTrue(proof['actual_forward_slot_reopened_twice']);self.assertFalse(proof['reverse_parent_used_for_ownership'])
  self.assertEqual(writer.rows[-1]['actual_child_index_in_parent'],-1)
 def test_unchanged_parent_wrong_index_foreign_and_current_slot_change_are_rejected(self):
  for defect in ('same-parent','foreign-reverse','changed-slot'):
   resolver,root,child,ForwardNode,_=self.resolver()
   if defect=='same-parent':child.parent=root
   elif defect=='foreign-reverse':child.parent.pid=200
   else:root.children[0]=ForwardNode('replacement')
   with self.assertRaises(ValueError):resolver.ancestors(child,root)
 def test_identity_change_on_second_slot_read_is_rejected(self):
  resolver,root,child,ForwardNode,_=self.resolver();calls=0
  def read(index):
   nonlocal calls
   calls+=1;return child if calls==1 else ForwardNode('replacement')
  root.get_child_at_index=read
  with self.assertRaisesRegex(ValueError,'reread'):resolver.ancestors(child,root)

class InventoryBudgetTests(unittest.TestCase):
 def test_runtime_journal_keeps_actual_counts_with_bounded_samples_without_guard_credit(self):
  import json,tempfile
  from pathlib import Path
  from native_desktop_factory import native_hit_identity_diagnostic_v33 as diag
  from native_desktop_factory.native_terminal_hit_diagnostic_v38 import bounded_runtime_journal
  with tempfile.TemporaryDirectory() as temporary:
   path=Path(temporary)/'facts.private.jsonl';writer=bounded_runtime_journal(diag,path)
   for index in range(2000):writer.append({'kind':'actual_native_inventory_deferral','ordinal':index,'ownership_reopened':True,'reason':'native_node_budget_cap'})
   writer.close();writer.close();rows=[json.loads(r) for r in path.read_text().splitlines()]
   self.assertEqual(len(rows),9);summary=rows[-1]
   self.assertEqual(summary['actual_record_counts']['actual_native_inventory_deferral'],2000)
   self.assertEqual(summary['omitted_diagnostic_samples'],1992);self.assertEqual(summary['native_predicates_skipped'],0)
   self.assertFalse(summary['native_actions_authorized']);self.assertEqual(writer.reference()['records'],9)
 def test_owned_exact_identity_duplicate_and_budget_have_distinct_retained_reasons(self):
  from native_desktop_factory.native_terminal_hit_diagnostic_v38 import checked_inventory_visit
  window=Node('frame');child=window.add(Node('panel'));writer=Writer();branches=[];seen=set()
  identity=lambda n:{'available':True,'identity_sha256':str(id(n))}
  def visit(node):return checked_inventory_visit(node,window,pid=100,ancestry=ancestry,identity=identity,seen=seen,maximum=1,depth=0,branches=branches,writer=writer)
  self.assertTrue(visit(window));self.assertFalse(visit(window));self.assertFalse(visit(child))
  self.assertEqual([b['reason'] for b in branches],['reopened_owned_identity_duplicate','native_node_budget_cap'])
  child.pid=200
  with self.assertRaisesRegex(ValueError,'ownership'):visit(child)
 def test_duplicate_identity_never_admits_unreachable_foreign_node(self):
  from native_desktop_factory.native_terminal_hit_diagnostic_v38 import checked_inventory_visit
  window=Node('frame');foreign=Node('frame')
  with self.assertRaisesRegex(ValueError,'foreign'):
   checked_inventory_visit(foreign,window,pid=100,ancestry=ancestry,identity=lambda n:{'available':True,'identity_sha256':'same-key'},seen={'same-key'},maximum=1,depth=0,branches=[],writer=Writer())
