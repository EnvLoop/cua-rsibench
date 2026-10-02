from types import SimpleNamespace
import unittest
from native_desktop_factory import native_hit_identity_diagnostic_v33 as diagnostic

API=SimpleNamespace(CoordType=SimpleNamespace(SCREEN='screen'))
class Node:
 def __init__(self,path,*,bus=':1.7',role='panel',pid=100,parent=None):self.path=path;self.app=SimpleNamespace(bus_name=bus);self.role=role;self.pid=pid;self.parent=parent;self.parent_reads=0
 def get_process_id(self):return self.pid
 def get_role_name(self):return self.role
 def get_parent(self):self.parent_reads+=1;return self.parent
 def get_component_iface(self):return SimpleNamespace(get_extents=lambda coord:SimpleNamespace(x=10,y=20,width=400,height=300))
 def get_name(self):raise AssertionError('Native names must not be read')
 def get_text(self):raise AssertionError('Native text must not be read')

class IdentityTests(unittest.TestCase):
 def test_foreign_window_same_process_remains_refused_with_native_identity_facts(self):
  owned=Node('/org/a11y/atspi/accessible/10',role='frame');foreign=Node('/org/a11y/atspi/accessible/20',role='dialog');child=Node('/org/a11y/atspi/accessible/21',parent=foreign)
  result=diagnostic.parent_diagnostic(child,owned,API)
  self.assertTrue(result['different_native_window_identity_observed']);self.assertFalse(result['native_owned_identity_in_chain']);self.assertFalse(result['same_pid_is_ownership_proof']);self.assertFalse(result['native_action_authorized']);self.assertEqual(result['status'],'missing_parent')
 def test_two_proxy_wrappers_same_bus_object_identity_are_diagnosed_without_acceptance(self):
  owned=Node('/org/a11y/atspi/accessible/10',role='frame');proxy=Node('/org/a11y/atspi/accessible/10',role='frame');child=Node('/org/a11y/atspi/accessible/11',parent=proxy)
  result=diagnostic.parent_diagnostic(child,owned,API)
  self.assertEqual(result['status'],'native_owned_identity_observed_proxy_mismatch');self.assertTrue(result['proxy_identity_mismatch_observed']);self.assertTrue(result['native_owned_identity_in_chain']);self.assertTrue(result['original_guard_refusal_preserved']);self.assertFalse(result['native_action_authorized'])
 def test_missing_parent_and_missing_native_fields_remain_unknown(self):
  owned=Node('/org/a11y/atspi/accessible/10',role='frame');child=Node('/org/a11y/atspi/accessible/11');del child.app
  result=diagnostic.parent_diagnostic(child,owned,API)
  self.assertEqual(result['status'],'missing_parent');self.assertFalse(result['parent_chain'][0]['identity']['available']);self.assertIn('app.bus_name',result['parent_chain'][0]['identity']['field_errors']);self.assertFalse(result['native_owned_identity_in_chain'])
 def test_existing_cap_refusal_preserves_all_bounded_facts_without_more_parent_reads(self):
  owned=Node('/org/a11y/atspi/accessible/10',role='frame');nodes=[Node('/org/a11y/atspi/accessible/'+str(100+i)) for i in range(33)]
  for index,node in enumerate(nodes[:-1]):node.parent=nodes[index+1]
  result=diagnostic.parent_diagnostic(nodes[0],owned,API)
  self.assertEqual(result['status'],'cap_refused');self.assertEqual(len(result['parent_chain']),32);self.assertEqual(nodes[31].parent_reads,0);self.assertEqual(nodes[32].parent_reads,0);self.assertFalse(result['native_action_authorized'])
 def test_geometry_failure_does_not_erase_mandatory_role_pid_identity_facts(self):
  owned=Node('/org/a11y/atspi/accessible/10',role='frame');child=Node('/org/a11y/atspi/accessible/11')
  def fail():raise RuntimeError('synthetic unsupported component')
  child.get_component_iface=fail
  result=diagnostic.parent_diagnostic(child,owned,API);row=result['parent_chain'][0]
  self.assertEqual(row['native_pid'],100);self.assertEqual(row['native_role'],'panel');self.assertTrue(row['identity']['available']);self.assertEqual(row['field_errors']['geometry'],'RuntimeError')

 def test_private_journal_preserves_mandatory_fields_before_optional_geometry_failure(self):
  import tempfile,json
  from pathlib import Path
  owned=Node('/org/a11y/atspi/accessible/10',role='frame');child=Node('/org/a11y/atspi/accessible/11')
  def fail():raise RuntimeError('synthetic unsupported component')
  child.get_component_iface=fail
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'facts.jsonl';writer=diagnostic.PrivateFacts(path)
   diagnostic.parent_diagnostic(child,owned,API,sink=writer.append);writer.close();rows=[json.loads(line) for line in path.read_bytes().splitlines()]
   self.assertTrue(any(row['stage']=='native_structural_field' and row['facts']['native_pid']==100 for row in rows));self.assertTrue(any(row['stage']=='native_structural_geometry' and row['facts']['field_errors'].get('geometry')=='RuntimeError' for row in rows));self.assertEqual(path.stat().st_mode&0o777,0o600);self.assertFalse(writer.reference()['actor_access_authorized'])

if __name__=='__main__':unittest.main()
