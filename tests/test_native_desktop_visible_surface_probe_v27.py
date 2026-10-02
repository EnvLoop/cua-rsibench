from types import SimpleNamespace
import unittest
from native_desktop_factory.native_visible_surface_probe_v27 import collection_queries,ancestors

class CollectionTests(unittest.TestCase):
 def api(self):return SimpleNamespace(StateSet=SimpleNamespace(new=lambda states:tuple(states)),MatchRule=SimpleNamespace(new=lambda *args:args),StateType=SimpleNamespace(VISIBLE=1,SHOWING=2,FOCUSED=3),CollectionMatchType=SimpleNamespace(ALL='all',ANY='any'),CollectionSortOrder=SimpleNamespace(CANONICAL='canonical'))
 def test_native_visible_and_focus_queries_are_finite_and_do_not_enumerate_tree(self):
  calls=[]
  class Collection:
   def get_matches(self,rule,sort,count,traverse):calls.append((rule,count,traverse));return ['visible'] if count==129 else []
  window=SimpleNamespace(get_collection_iface=lambda:Collection());visible,focus=collection_queries(self.api(),window)
  self.assertEqual(visible,['visible']);self.assertIsNone(focus);self.assertEqual([x[1] for x in calls],[129,2]);self.assertEqual(calls[0][0][0],(1,2));self.assertEqual(calls[1][0][0],(3,))
 def test_overflow_and_ambiguous_focus_are_not_partial_safe_metadata(self):
  for mode in ['overflow','focus']:
   class Collection:
    def get_matches(self,rule,sort,count,traverse):return list(range(129)) if mode=='overflow' else ([] if count==129 else [1,2])
   with self.assertRaises(ValueError):collection_queries(self.api(),SimpleNamespace(get_collection_iface=lambda:Collection()))
 def test_requested_native_hit_must_have_bounded_owned_window_ancestor(self):
  window=SimpleNamespace();node=SimpleNamespace(get_parent=lambda:window)
  self.assertEqual(ancestors(node,window),[node,window])
  foreign=SimpleNamespace(get_parent=lambda:None)
  with self.assertRaisesRegex(ValueError,'owned window'):ancestors(foreign,window)

if __name__=='__main__':unittest.main()
