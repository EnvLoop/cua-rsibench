"""Production guard readiness with real lease; synthetic UI, optional saved v7 pair."""
from hashlib import sha256
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_odoo_native_surface_real_lease_v8 import held_fixture, native, workers
from cursibench import native_surface_guard_policy_v1 as policy


class NativeReadinessTests(unittest.TestCase):
    def test_genuine_busy_then_ready_retains_images_before_observation(self):
        with held_fixture() as (adapter,page,private,root):
            page.busy=True
            page.when_wait=lambda n:setattr(page,'busy',False) if n==3 else None
            obs,_=adapter.observe_for_model()
            rows=sorted((root/'surface-guard').glob('readiness-turn-000-[0-9][0-9].private.json'))
            self.assertEqual(len(rows),3)
            self.assertTrue(json.loads(rows[0].read_bytes())['loading']['busy'])
            self.assertFalse(json.loads(rows[-1].read_bytes())['loading']['busy'])
            for row in rows:
                data=json.loads(row.read_bytes())
                workers.native_ref_bytes(root,data['image'])
                self.assertEqual(data['lease_check']['status'],'active')
                self.assertFalse(data['gui_driver_called'])
            self.assertEqual(page.calls,[])
            self.assertEqual(obs.step,0)

    def test_rpc_finishing_restarts_global_quiet_interval(self):
        with held_fixture() as (adapter,page,private,root):
            request=SimpleNamespace(resource_type='xhr')
            page.events['request'](request)
            page.when_wait=lambda n:page.events['requestfinished'](request) if n==3 else None
            adapter.observe_for_model()
            self.assertEqual(page.waits,5)
            self.assertEqual(page.calls,[])
            self.assertEqual(adapter._pending_requests,{})

    def test_streams_do_not_block_ready_and_failed_rpc_settles(self):
        with held_fixture() as (adapter,page,private,root):
            for kind in ('websocket','eventsource','image'):
                page.events['request'](SimpleNamespace(resource_type=kind))
            req=SimpleNamespace(resource_type='fetch')
            page.events['request'](req);page.events['requestfailed'](req)
            adapter.observe_for_model()
            self.assertEqual(page.waits,2)
            self.assertEqual(adapter._pending_requests,{})

    def test_permanent_disabled_target_does_not_wait_and_rejection_is_truthful(self):
        with held_fixture() as (adapter,page,private,root):
            page.disabled=True
            obs,_=adapter.observe_for_model()
            self.assertEqual(page.waits,2)
            action=adapter.parse_current_action('{"type":"click","target":{"x":350,"y":50}}')
            result=adapter.dispatch(action)
            self.assertEqual(result['status'],'rejected')
            self.assertEqual(page.calls,[])
            self.assertEqual(adapter.step,1)
            rejection=json.loads((root/'surface-guard/rejected-turn-000.private.json').read_bytes())
            capsule=json.loads(workers.native_ref_bytes(root,result['public_contract_receipt']['native_surface_guard']))
            self.assertEqual(capsule['decision']['reason'],'target_not_current_and_safe')
            self.assertEqual(capsule['receipt']['driver_result'],'not_attempted')
            self.assertFalse(rejection['gui_driver_called'])
            fresh,_=adapter.observe_for_model()
            self.assertNotEqual(fresh.frame_id,obs.frame_id)
            self.assertEqual(fresh.previous_action_result['status'],'rejected')

    def test_actual_production_recorder_saves_native_reason_then_stops(self):
        with held_fixture() as (adapter,page,private,root):
            page.disabled=True
            evaluator=workers.evaluator_module(workers.public_binding())
            journal=evaluator.HoldoutJournal(adapter,page,root)
            with self.assertRaisesRegex(RuntimeError,'target_not_current_and_safe') as caught:
                journal.act('click',phase='positive',target={'x':350,'y':50})
            self.assertEqual(caught.exception.code,'target_not_current_and_safe')
            row=json.loads((root/'actions/step-000-rejected.private.json').read_bytes())
            capsule=json.loads(workers.native_ref_bytes(root,row['contract_receipt']['native_surface_guard']))
            self.assertEqual(row['reason'],capsule['decision']['reason'])
            self.assertFalse(row['gui_driver_called'])
            self.assertFalse(row['applied_inferred'])
            self.assertTrue(row['turn_consumed'])
            self.assertEqual(journal.trace,[])
            self.assertEqual(page.calls,[])
            self.assertFalse(list((root/'actions').glob('*-result.private.json')))

    def test_busy_timeout_retains_all_raws_and_never_dispatches_or_replays(self):
        for mode in ('dom','rpc'):
            with self.subTest(mode=mode),held_fixture() as (adapter,page,private,root):
                page.busy=mode=='dom'
                if mode=='rpc':page.events['request'](SimpleNamespace(resource_type='xhr'))
                with self.assertRaisesRegex(native.GuardHardStop,'loading_timeout_no_replay'):
                    adapter.observe_for_model()
                self.assertEqual(page.waits,native.READINESS_MAX_SAMPLES)
                self.assertEqual(page.calls,[])
                self.assertIsNone(adapter.latest)
                self.assertEqual(adapter.step,0)
                self.assertEqual(len(list((root/'surface-guard').glob('readiness-turn-000-*.png'))),24)
                failure=json.loads((root/'surface-guard/readiness-failure-000-000.private.json').read_bytes())
                self.assertFalse(failure['nonce_issued'])
                with self.assertRaisesRegex(native.GuardHardStop,'quarantined_no_replay'):
                    adapter.dispatch({})
                self.assertFalse(list((root/'surface-guard').glob('turn-000/*intent*')))

    def test_native_account_url_and_lease_loss_stop_with_durable_capture(self):
        for change in ('account','url','lock'):
            with self.subTest(change=change),held_fixture() as (adapter,page,private,root):
                if change=='account':page.uid='res.partner:999'
                elif change=='url':page.url='https://outside.invalid/odoo/purchase/42'
                else:(private/'worker-operation.lock').write_bytes(b'{}')
                with self.assertRaises((native.GuardHardStop,policy.GuardError)):
                    adapter.observe_for_model()
                self.assertEqual(page.calls,[])
                self.assertIsNone(adapter.latest)
                self.assertTrue((root/'surface-guard/readiness-turn-000-00.png').exists())
                self.assertTrue((root/'surface-guard/readiness-turn-000-00-native.private.json').exists())
                self.assertTrue((root/'surface-guard/readiness-failure-000-000.private.json').exists())

    def test_uncertain_driver_is_not_replayed(self):
        with held_fixture() as (adapter,page,private,root):
            adapter.observe_for_model()
            action=adapter.parse_current_action('{"type":"click","target":{"x":50,"y":50}}')
            def broken(*_args,**_kwargs):
                page.calls.append(('started',));raise OSError('synthetic unknown completion')
            page.mouse.click=broken
            with self.assertRaises(native.GuardDriverUncertain):adapter.dispatch(action)
            self.assertEqual(page.calls,[('started',)])
            capsule=json.loads((root/'surface-guard/turn-000/receipt.private.json').read_bytes())
            self.assertEqual(capsule['receipt']['driver_result'],'unknown')
            with self.assertRaises(native.GuardHardStop):adapter.dispatch(action)
            self.assertEqual(page.calls,[('started',)])

    def test_actual_saved_loading_pair_rejection_remains_rejection(self):
        supplied=os.environ.get('ENVLOOP_ODOO_V7_LOADING_PAIR')
        if not supplied:self.skipTest('Set private saved turn-003 directory; no native/provider IO')
        root=Path(supplied)
        obs=json.loads((root/'observation-native.private.json').read_bytes())
        cur=json.loads((root/'predispatch-native.private.json').read_bytes())
        capsule=json.loads((root/'receipt.private.json').read_bytes())
        for phase in ('observation','predispatch'):
            image=(root/(phase+'.png')).read_bytes()
            self.assertEqual(sha256(image).hexdigest(),capsule['observed' if phase=='observation' else 'current']['raw_image']['sha256'])
        at=lambda target:target['bounds'][0]<=1307<target['bounds'][0]+target['bounds'][2] and target['bounds'][1]<=868<target['bounds'][1]+target['bounds'][3]
        self.assertTrue(any(not r['enabled'] for r in obs['targets'] if at(r)))
        self.assertTrue(any(r['enabled'] for r in cur['targets']+cur['hits'] if at(r)))
        self.assertEqual(capsule['decision']['status'],'rejected')
        self.assertEqual(capsule['decision']['reason'],'target_not_current_and_safe')
        self.assertEqual(capsule['receipt']['driver_result'],'not_attempted')
        rederived=policy.decision(capsule['observed'],capsule['current'],capsule['action'],lease_check=lambda _:capsule['decision']['lease_check'],now=capsule['audit_clock'])
        self.assertEqual(rederived,capsule['decision'])

    def test_actual_saved_loading_pair_is_retained_by_request_barrier_fixture(self):
        supplied=os.environ.get('ENVLOOP_ODOO_V7_LOADING_PAIR')
        if not supplied:self.skipTest('Set private saved turn-003 directory; no native/provider IO')
        original=Path(supplied)
        rows=[json.loads((original/(phase+'-native.private.json')).read_bytes()) for phase in ('observation','predispatch')]
        images=[(original/(phase+'.png')).read_bytes() for phase in ('observation','predispatch')]
        # Only event timing is synthetic. Original raster/targets are reopened,
        # and no source-only test claims a new native qualification attempt.
        with held_fixture() as (adapter,page,private,root):
            base_evaluate=page.evaluate
            phase=[0]
            def evaluate(script,args=None):
                if script!=native.NATIVE_CONTEXT_JS:return base_evaluate(script,args)
                value=copy.deepcopy(rows[phase[0]])
                value.update(schema='odoo-current-native-surface-v8',account_principal=page.uid,
                    principal_witness=base_evaluate(script,args)['principal_witness'],hits=[])
                return value
            page.evaluate=evaluate
            page.screenshot=lambda **_:images[phase[0]]
            request=SimpleNamespace(resource_type='xhr')
            page.events['request'](request)
            def settle(n):
                if n==3:
                    phase[0]=1;page.events['requestfinished'](request)
            page.when_wait=settle
            observed,_=adapter.observe_for_model()
            self.assertEqual(observed.screenshot_bytes,images[1])
            captures=sorted((root/'surface-guard').glob('readiness-turn-000-*.png'))
            self.assertEqual(captures[0].read_bytes(),images[0])
            self.assertEqual(captures[-1].read_bytes(),images[1])
            self.assertEqual(page.calls,[])
