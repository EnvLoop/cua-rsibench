from types import SimpleNamespace
import unittest
from native_desktop_factory import native_window_relation_diagnostic_v35 as relations
from native_desktop_factory import native_hit_identity_diagnostic_v33 as identity
from native_desktop_factory import native_visible_surface_probe_v31 as preserved
from tests.test_native_desktop_visible_surface_probe_v30 import Node as HitNode,API as HITAPI,ancestry
from tests.test_native_desktop_hit_identity_diagnostic_v33 import Node
API=SimpleNamespace(CoordType=SimpleNamespace(SCREEN='screen'))

class RelationTests(unittest.TestCase):
 def test_actual_frame_extents_derive_decorated_box_without_guessed_offset(self):
  extents=relations.frame_extents('_NET_FRAME_EXTENTS(CARDINAL) = 0, 0, 24, 0\nWM_TRANSIENT_FOR: not found.');self.assertEqual(relations.decorated_geometry([0,51,1280,749],extents),[0,27,1280,773])
  missing=relations.frame_extents('_NET_FRAME_EXTENTS: not found.');self.assertTrue(missing['unknown_not_zero']);self.assertIsNone(relations.decorated_geometry([0,51,1280,749],missing))
 def test_explicit_transient_and_direct_parent_child_tree_are_parsed_without_inference(self):
  self.assertEqual(relations.transient('WM_TRANSIENT_FOR(WINDOW): window id # 0x100')['xid'],256)
  raw='Root window id: 0x1\nParent window id: 0x200\n2 children:\n 0x300 (has no name): () 20x20+0+0\n 0x301 (has no name): () 20x20+0+0\n';result=relations.direct_tree(raw);self.assertEqual(result['parent_xid'],512);self.assertEqual(result['child_xids'],[768,769]);self.assertFalse(result['recursive_tree_enumerated'])
  self.assertEqual(relations.direct_tree('Root window id: 0x1\nParent window id: 0x200\n0 children.\n')['child_xids'],[])
 def test_incomplete_or_overflow_tree_and_extents_refuse(self):
  for raw in ['Root window id: 0x1\nParent window id: 0x200\n2 children:\n 0x300 data\n','Root window id: 0x1\nParent window id: 0x200\n65 children:\n']:
   with self.assertRaises(ValueError):relations.direct_tree(raw)
  with self.assertRaises(ValueError):relations.frame_extents('_NET_FRAME_EXTENTS(CARDINAL) = 0, 0, 99999, 0')
 def test_actual_relation_target_identity_is_recorded_but_member_child_or_embedding_does_not_authorize(self):
  owned=Node('/org/a11y/atspi/accessible/10',role='frame');node=Node('/org/a11y/atspi/accessible/20',role='frame')
  for kind in [5,7,12,13,14]:
   with self.subTest(relation_type=kind):
    node.get_relation_set=lambda:[SimpleNamespace(get_relation_type=lambda:kind,get_n_targets=lambda:1,get_target=lambda index:owned)]
    result=relations.relation_facts(node,owned,API,structural=identity.structural_facts)
    self.assertEqual(result['relations'][0]['native_relation_type'],kind);self.assertEqual(result['relations'][0]['targets'][0]['identity']['identity_sha256'],identity.identity(owned)['identity_sha256']);self.assertFalse(result['native_ownership_authorized'])
 def test_relation_and_target_caps_preserve_actual_counts_without_enumerating_more(self):
  owned=Node('/org/a11y/atspi/accessible/10',role='frame');node=Node('/org/a11y/atspi/accessible/20',role='frame');node.get_relation_set=lambda:[None]*17
  result=relations.relation_facts(node,owned,API,structural=identity.structural_facts);self.assertEqual(result['reported_relation_count'],17);self.assertEqual(result['relation_errors']['get_relation_set'],'ValueError')
  called=[];node.get_relation_set=lambda:[SimpleNamespace(get_relation_type=lambda:12,get_n_targets=lambda:9,get_target=lambda index:called.append(index))]
  result=relations.relation_facts(node,owned,API,structural=identity.structural_facts);self.assertEqual(result['relations'][0]['reported_target_count'],9);self.assertEqual(called,[]);self.assertFalse(result['native_ownership_authorized'])
 def test_preserved_physical_hit_uses_screen_coordinates_for_extents_and_hit(self):
  window=HitNode('frame');leaf=window.add(HitNode('table cell'));window.hit=leaf;calls=[]
  for node in [window,leaf]:
   original=node.get_component_iface
   def component(original=original):
    old=original()
    return SimpleNamespace(get_extents=lambda coord:calls.append(('extent',coord)) or old.get_extents(coord),get_accessible_at_point=lambda x,y,coord:calls.append(('hit',coord,x,y)) or old.get_accessible_at_point(x,y,coord))
   node.get_component_iface=component
  result=preserved.physical_hit(HITAPI,window,[40,40],pid=100,viewport=[400,300],ancestry=ancestry);self.assertIs(result[0],leaf);self.assertTrue(all(row[1]=='screen' for row in calls));self.assertTrue(all(row[2:]==(40,40) for row in calls if row[0]=='hit'))

if __name__=='__main__':unittest.main()
