"""Native reference controls: hydration and all facets, no direct mutation."""
import unittest
from tools.odoo_v066_scale_recipes_v2 import clear_current_search_facets


class FacetReferenceTests(unittest.TestCase):
    def fixture(self,count=3,refuse=False):
        events=[];state={'count':0,'hydrated':False}
        class Facet:
            def is_visible(self):return True
        class Facets:
            def count(self):return state['count']
            def nth(self,index):return Facet()
        class Box:
            @property
            def first(self):return self
            def wait_for(self,**kwargs):
                state['hydrated']=True;state['count']=count;events.append(('visible_searchbox',kwargs))
        class Page:
            def get_by_role(self,role):
                self.role=role;return Box()
            def locator(self,selector):
                if not state['hydrated']:raise AssertionError('facet inspected before native hydration')
                if selector!='.o_searchview .o_facet_remove':raise AssertionError('task-specific selector')
                return Facets()
            def evaluate(self,*_args):raise AssertionError('direct DOM mutation forbidden')
        class Journal:
            def act(self,kind,**kwargs):
                events.append(('native_journal_action',kind,kwargs['phase']))
                if refuse:raise RuntimeError('actual guard rejected current facet')
                state['count']-=1
        return Page(),Journal(),state,events

    def test_all_native_facets_removed_only_through_journal_after_hydration(self):
        page,journal,state,events=self.fixture()
        clear_current_search_facets(page,journal,'positive')
        self.assertEqual(state['count'],0)
        self.assertEqual(events[0][0],'visible_searchbox')
        self.assertEqual(sum(row[0]=='native_journal_action' for row in events),3)

    def test_actual_rejection_stops_without_retry_or_direct_clear(self):
        page,journal,state,events=self.fixture(refuse=True)
        with self.assertRaisesRegex(RuntimeError,'guard rejected'):clear_current_search_facets(page,journal,'negative')
        self.assertEqual(state['count'],3)
        self.assertEqual(sum(row[0]=='native_journal_action' for row in events),1)

    def test_zero_facets_does_not_invent_an_action(self):
        page,journal,state,events=self.fixture(count=0)
        clear_current_search_facets(page,journal,'positive')
        self.assertEqual(len(events),1)


if __name__=='__main__':unittest.main()
