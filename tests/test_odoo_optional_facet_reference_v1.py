"""Actual v12 guard/Unix lease and pinned recorder; no native/provider service."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import native_reference_facet_v1 as ref
from enterprise_fallback.odoo18 import native_surface_workers_v12 as workers
from tools import odoo_v066_scale_recipes_v3 as recipes
from tools import odoo_v066_native_reference_qualification_v1 as facade
from tests.test_odoo_native_surface_real_lease_v12 import held_fixture


class Handle:
    def __init__(self,box):self.box=box;self.disposed=False
    def bounding_box(self):return self.box
    def dispose(self):self.disposed=True
class Locator:
    def __init__(self,handles):self.handles=handles
    @property
    def first(self):return self
    def element_handles(self):return self.handles
    def bounding_box(self,*args,**kwargs):raise AssertionError('locator auto-wait forbidden')


class OptionalFacetTests(unittest.TestCase):
    def recorder(self):return ref.recorder_module(workers.public_binding(),ref.reference_binding())
    def test_disappeared_candidate_wait_is_one_real_trace_and_next_frame_nonce(self):
        with held_fixture() as (adapter,page,_private,root):
            page.locator=lambda selector:Locator([])
            recorder=self.recorder();journal=recorder.ActionJournal(adapter,page,root)
            journal.act('click',phase='positive',optional_facet=True)
            self.assertEqual(len(journal.trace),1);self.assertEqual(adapter.step,1);self.assertEqual(page.calls,[])
            intent=json.loads((root/'actions/step-000-intent.private.json').read_bytes())
            self.assertEqual(intent['normalized_action']['type'],'wait');self.assertEqual(intent['normalized_action']['duration_ms'],100)
            self.assertTrue(intent['optional_native_facet_resolution']['actual_wait_selected_before_intent'])
            capsule=json.loads(workers.native_ref_bytes(root,journal.trace[0]['contract_receipt']['native_surface_guard']))
            self.assertEqual(capsule['receipt']['status'],'applied');self.assertEqual(capsule['receipt']['driver_result'],'succeeded')
            first=intent['frame_id'];journal.act('wait',phase='negative',duration_ms=50)
            second=json.loads((root/'actions/step-001-intent.private.json').read_bytes())
            self.assertNotEqual(first,second['frame_id']);self.assertEqual(len(journal.trace),2)
            self.assertEqual(journal.pre_intent_rejections,[])
    def test_current_handle_resolved_after_observation_and_disposed_before_driver(self):
        with held_fixture() as (adapter,page,_private,root):
            events=[];handle=Handle({'x':320,'y':30,'width':100,'height':40})
            original=adapter.observe_for_model
            def observe(**kwargs):events.append('actual_native_observe');return original(**kwargs)
            adapter.observe_for_model=observe
            def locator(selector):events.append('current_native_query');self.assertEqual(selector,ref.SELECTOR);return Locator([handle])
            page.locator=locator;journal=self.recorder().ActionJournal(adapter,page,root)
            journal.act('click',phase='positive',optional_facet=True)
            self.assertEqual(events[:2],['actual_native_observe','current_native_query']);self.assertTrue(handle.disposed)
            self.assertEqual(page.calls,[('click',370,50)]);self.assertEqual(adapter.step,1)
    def test_duplicate_handle_is_fatal_before_intent_and_no_other_object_click(self):
        with held_fixture() as (adapter,page,_private,root):
            page.locator=lambda _:Locator([Handle(None),Handle(None)])
            journal=self.recorder().ActionJournal(adapter,page,root)
            with self.assertRaisesRegex(ValueError,'duplicate_handle'):journal.act('click',phase='negative',optional_facet=True)
            self.assertEqual(page.calls,[]);self.assertFalse(list((root/'actions').glob('*intent.private.json')))
            self.assertEqual(journal.trace,[]);self.assertEqual(adapter.step,0)
            self.assertTrue((root/'frames/step-000.png').exists())
    def test_detached_or_hidden_handle_becomes_wait_not_a_different_control(self):
        with held_fixture() as (adapter,page,_private,root):
            handle=Handle(None);page.locator=lambda _:Locator([handle]);journal=self.recorder().ActionJournal(adapter,page,root)
            journal.act('click',phase='positive',optional_facet=True)
            self.assertTrue(handle.disposed);self.assertEqual(page.calls,[])
            intent=json.loads((root/'actions/step-000-intent.private.json').read_bytes())
            self.assertNotIn('target',intent['normalized_action']);self.assertEqual(intent['normalized_action']['type'],'wait')
    def test_signature_no_arbitrary_selector_or_stale_locator(self):
        with held_fixture() as (adapter,page,_private,root):
            page.locator=lambda _:(_ for _ in ()).throw(AssertionError('should not query'))
            journal=self.recorder().ActionJournal(adapter,page,root)
            with self.assertRaisesRegex(RuntimeError,'signature_invalid'):journal.act('click',phase='positive',optional_facet=True,ref='save')
            self.assertEqual(page.calls,[])
    def test_source_binding_and_candidate_copy_leave_v12_modules_unchanged(self):
        binding=workers.public_binding();reference=ref.reference_binding();old=workers.evaluator_module(binding)
        old_class=old.HoldoutJournal;old_recipes=old.recipes;new=ref.candidate_module(binding,reference)
        self.assertIs(old.HoldoutJournal,old_class);self.assertIs(old.recipes,old_recipes)
        self.assertIsNot(new.HoldoutJournal,old_class)
        self.assertIsNot(new,old)
        self.assertIs(new.recipes,recipes)
        self.assertEqual(workers.public_binding(),binding)
        with self.assertRaises(ValueError):ref.validate_reference_binding({**reference,'old_reference_control_credit':5})
    def test_metadata_prepare_keeps_full_twenty_hundred_all_family_rosters(self):
        from tests.test_odoo_native_material_qualification_v2 import roster
        for split,count in [('train',20),('selection',20),('official_hidden',100)]:
            metadata=roster(split);metadata['schema']=facade.core.ROSTER_SCHEMA;plan,public=facade.prepare(metadata)
            facade.validate_plan(plan)
            self.assertEqual(plan['native_core_plan']['tasks'],metadata['tasks'])
            self.assertEqual(public['task_count'],count)
            self.assertEqual(set(r['family'] for r in metadata['tasks']),{'purchase','inventory','sales','crm'})
            self.assertEqual(plan['historical_reference_credit'],0)
            self.assertFalse(plan['formal_registration_performed'])

    def test_reference_facade_uses_fresh_copied_globals_only(self):
        reference=ref.reference_binding();old=facade.core.run.__globals__['workers'];new=facade._facade(reference)
        self.assertIs(facade.core.run.__globals__['workers'],old)
        self.assertIsNot(new.run.__globals__['workers'],old)
        with self.assertRaises(ValueError):facade.validate_plan({'schema':facade.SCHEMA})

if __name__=='__main__':unittest.main()
