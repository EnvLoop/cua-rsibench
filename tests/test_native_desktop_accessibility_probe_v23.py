"""Actual probe algorithm on synthetic native API objects, no desktop calls."""
from types import SimpleNamespace
import unittest
from native_desktop_factory.native_accessibility_probe_v23 import atspi_targets

class State:
 def __init__(self,states):self.states=set(states)
 def contains(self,value):return value in self.states
class Node:
 def __init__(self,role,states,bounds,children=()):
  self.role=role;self.state=State(states);self.bounds=bounds;self.children=list(children);self.parent=None;self.hit=self
  for child in children:child.parent=self
 @property
 def childCount(self):return len(self.children)
 @property
 def name(self):
  if self.role=='text':raise AssertionError('Task text must not be read')
  return 'Share' if self.role=='push button' else 'Native application'
 def __getitem__(self,index):return self.children[index]
 def getState(self):return self.state
 def getRoleName(self):return self.role
 def queryComponent(self):return self
 def getExtents(self,_):return SimpleNamespace(x=self.bounds[0],y=self.bounds[1],width=self.bounds[2],height=self.bounds[3])
 def getAccessibleAtPoint(self,*args):return self.hit
API=SimpleNamespace(XY_SCREEN=0,STATE_VISIBLE='visible',STATE_SHOWING='showing',STATE_ENABLED='enabled',STATE_SENSITIVE='sensitive',STATE_EDITABLE='editable',STATE_FOCUSED='focused')
class ProbeTests(unittest.TestCase):
 def test_actual_native_state_geometry_and_hit_are_required_no_text_read(self):
  field=Node('text',['visible','showing','enabled','sensitive','editable','focused'],[20,30,100,40]);window=Node('frame',['visible','showing','enabled','sensitive'],[0,0,1280,800],[field]);window.hit=field
  targets,focus,visited=atspi_targets(API,window,viewport=[1280,800]);self.assertEqual(visited,2);self.assertEqual(focus[0]['bounds'],[20,30,100,40]);self.assertTrue(focus[0]['keyboard']);self.assertFalse(focus[0]['obscured'])
 def test_disabled_native_field_is_not_enabled_by_a_canvas(self):
  field=Node('text',['visible','showing','editable'],[20,30,100,40]);window=Node('frame',['visible','showing','enabled','sensitive'],[0,0,1280,800],[field]);window.hit=field
  targets,focus,_=atspi_targets(API,window,viewport=[1280,800]);self.assertFalse(targets[-1]['enabled']);self.assertFalse(targets[-1]['keyboard'])
 def test_missing_native_hit_is_obscured_and_share_is_unsafe(self):
  button=Node('push button',['visible','showing','enabled','sensitive'],[20,30,100,40]);window=Node('frame',['visible','showing','enabled','sensitive'],[0,0,1280,800],[button]);window.hit=None
  targets,_,_=atspi_targets(API,window,viewport=[1280,800]);self.assertTrue(all(t['obscured'] for t in targets));self.assertFalse(targets[-1]['enabled']);self.assertEqual(targets[-1]['actions'],[])

if __name__=='__main__':unittest.main()
