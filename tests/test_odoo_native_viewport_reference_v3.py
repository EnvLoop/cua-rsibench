"""Actual v13 guard/Unix lease and pinned recorder; no native/provider service."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import native_reference_viewport_v3 as ref
from enterprise_fallback.odoo18 import native_surface_workers_v13 as workers
from tools import odoo_v066_scale_recipes_v5 as recipes
from tools import odoo_v066_native_reference_qualification_v3 as facade
from tests.test_odoo_native_surface_real_lease_v13 import held_fixture


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


class ViewportReferenceTests(unittest.TestCase):
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
    def test_offviewport_current_candidate_scrolls_then_fresh_observation_and_original_click(self):
        with held_fixture() as (adapter,page,_private,root):
            box={'x':765,'y':986,'width':70,'height':40};events=[]
            class CurrentHandle:
                def bounding_box(self):events.append(('resolve',adapter.step));return dict(box)
                def dispose(self):events.append(('dispose',adapter.step))
            locator=Locator([CurrentHandle()])
            wheel=page.mouse.wheel
            def scroll(dx,dy):wheel(dx,dy);box['x']-=dx;box['y']-=dy
            page.mouse.wheel=scroll
            original_observe=adapter.observe_for_model
            def observe(**kwargs):events.append(('observe',adapter.step));return original_observe(**kwargs)
            adapter.observe_for_model=observe
            journal=self.recorder().ActionJournal(adapter,page,root)
            journal.act('click',phase='positive',locator=locator)
            intents=[json.loads((root/f'actions/step-{n:03d}-intent.private.json').read_bytes()) for n in range(2)]
            self.assertEqual([i['normalized_action']['type'] for i in intents],['scroll','click'])
            self.assertEqual(intents[0]['normalized_action']['target'],{'x':720,'y':500})
            self.assertEqual(intents[1]['normalized_action']['target'],{'x':800,'y':526})
            self.assertNotEqual(intents[0]['frame_id'],intents[1]['frame_id'])
            self.assertEqual(adapter.step,2);self.assertEqual(len(journal.trace),2)
            self.assertEqual(events,[('observe',0),('resolve',0),('dispose',0),('observe',1),('resolve',1),('dispose',1)])
            self.assertEqual(page.calls,[('move',(720,500)),('wheel',(0,480)),('click',800,526)])
            self.assertTrue(intents[0]['native_candidate_viewport_resolution']['original_action_deferred'])
            for trace in journal.trace:
                capsule=json.loads(workers.native_ref_bytes(root,trace['contract_receipt']['native_surface_guard']))
                self.assertEqual(capsule['receipt']['status'],'applied');self.assertEqual(capsule['receipt']['driver_result'],'succeeded')

    def test_scroll_unknown_io_never_replays_or_clicks_candidate(self):
        with held_fixture() as (adapter,page,_private,root):
            def unknown(*args):page.calls.append(('wheel_unknown',args));raise TimeoutError('synthetic uncertain native wheel')
            page.mouse.wheel=unknown
            journal=self.recorder().ActionJournal(adapter,page,root)
            locator=Locator([Handle({'x':765,'y':986,'width':70,'height':40})])
            with self.assertRaises(Exception):journal.act('click',phase='positive',locator=locator)
            self.assertFalse(any(call[0]=='click' for call in page.calls));self.assertEqual(sum(c[0]=='wheel_unknown' for c in page.calls),1)
            self.assertTrue((root/'actions/step-000-intent.private.json').exists())
            self.assertFalse((root/'actions/step-001-intent.private.json').exists())
            self.assertEqual(journal.trace,[])
            capsule=json.loads((root/'surface-guard/turn-000/guard.private.json').read_bytes()) if (root/'surface-guard/turn-000/guard.private.json').exists() else None
            if capsule is not None:self.assertNotEqual(capsule['receipt']['status'],'applied')

    def test_native_ownership_rejection_stops_before_scroll_driver(self):
        with held_fixture() as (adapter,page,_private,root):
            calls=[0];observe=adapter.observe_for_model
            def current(**kwargs):
                value=observe(**kwargs);page.uid='res.partner:foreign';return value
            adapter.observe_for_model=current
            journal=self.recorder().ActionJournal(adapter,page,root)
            with self.assertRaises(Exception):journal.act('click',phase='positive',locator=Locator([Handle({'x':765,'y':986,'width':70,'height':40})]))
            self.assertFalse(any(c[0] in ('wheel','click') for c in page.calls))
            self.assertFalse((root/'actions/step-001-intent.private.json').exists())

    def test_scroll_bound_missing_and_duplicate_candidates_fail_without_alternate_click(self):
        with held_fixture() as (adapter,page,_private,root):
            journal=self.recorder().ActionJournal(adapter,page,root)
            with self.assertRaisesRegex(RuntimeError,'scroll_bound_exhausted'):
                journal.act('click',phase='positive',locator=Locator([Handle({'x':765,'y':986,'width':70,'height':40})]))
            self.assertEqual(sum(c[0]=='wheel' for c in page.calls),8);self.assertEqual(len(journal.trace),8)
            self.assertFalse(any(c[0]=='click' for c in page.calls));self.assertFalse((root/'actions/step-008-intent.private.json').exists())
        for handles in ([],[Handle(None),Handle(None)],[Handle(None)]):
            with held_fixture() as (adapter,page,_private,root):
                journal=self.recorder().ActionJournal(adapter,page,root)
                with self.assertRaises(ValueError):journal.act('click',phase='positive',locator=Locator(handles))
                self.assertEqual(page.calls,[]);self.assertFalse((root/'actions/step-000-intent.private.json').exists())

    def test_actual_saved_offviewport_action_reopened_without_original_changes(self):
        import os
        from hashlib import sha256
        from io import BytesIO
        from PIL import Image
        root=os.environ.get('ENVLOOP_ODOO_RETAINED_V13_VIEWPORT_ATTEMPT')
        if not root:self.skipTest('optional private original attempt is not configured')
        root=Path(root);image_path=root/'frames/step-009.png';action_path=root/'actions/step-009-assistant.json'
        before=[sha256(path.read_bytes()).hexdigest() for path in (image_path,action_path)]
        action=json.loads(action_path.read_bytes())
        with Image.open(BytesIO(image_path.read_bytes())) as image:width,height=image.size
        self.assertEqual(action['type'],'click');self.assertTrue(action['target']['y']>=height)
        self.assertEqual((width,height),(1440,1000))
        with held_fixture() as (adapter,page,_private,out):
            observation,_=adapter.observe_for_model()
            x,y=action['target']['x'],action['target']['y']
            resolved,metadata=ref.resolve_native_candidate_payload(Locator([Handle({'x':x-35,'y':y-20,'width':70,'height':40})]),observation,{'type':'click'})
            self.assertEqual(resolved['type'],'scroll');self.assertEqual(resolved['dy'],480)
            self.assertTrue(metadata['original_action_deferred']);self.assertNotEqual(resolved.get('target'),action['target'])
        self.assertEqual(before,[sha256(path.read_bytes()).hexdigest() for path in (image_path,action_path)])

    def test_scroll_actions_use_original_total_turn_budget(self):
        with held_fixture() as (adapter,page,_private,root):
            journal=self.recorder().ActionJournal(adapter,page,root)
            journal.trace=[{'fixture_prior_turn':n} for n in range(89)];adapter.step=89;adapter.previous_result={'status':'applied','code':'ok'}
            with self.assertRaisesRegex(RuntimeError,'action_or_wall_budget_exceeded'):
                journal.act('click',phase='positive',locator=Locator([Handle({'x':765,'y':986,'width':70,'height':40})]))
            self.assertEqual(len(journal.trace),90);self.assertEqual(adapter.step,90)
            self.assertEqual(sum(c[0]=='wheel' for c in page.calls),1);self.assertFalse(any(c[0]=='click' for c in page.calls))
            self.assertFalse((root/'actions/step-090-intent.private.json').exists())

    def test_source_binding_and_candidate_copy_leave_v13_modules_unchanged(self):
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
