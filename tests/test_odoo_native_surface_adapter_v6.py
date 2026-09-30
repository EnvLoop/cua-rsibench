"""Current safety metadata and real saved raster deltas; no native/provider IO."""
import copy
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
from cursibench import native_surface_guard_policy_v1 as policy
from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18 import odoo_v066_native_surface_adapter_v6 as adapter
from enterprise_fallback.odoo18.odoo_native_surface_evidence_v6 import read_ref


def image():
    stream=BytesIO();Image.new('RGB',(1440,1000),'white').save(stream,'PNG');return stream.getvalue()


class Boundary:
    """Explicit unit fixture; native worker wiring uses the real lock helper."""
    def __init__(self,*,store,page,started,expires,**_kwargs):
        self.store=store;self.page=page;self.active=True;self.n=0
        window=policy.digest({'pid':os.getpid(),'page_object':id(page),'origin':'http://127.0.0.1:8078'})
        proof=store.json('unit-lease.private.json',{'schema':'odoo-native-held-lease-evidence-v6',
            'fixture_only':True,'origin':'http://127.0.0.1:8078','native_avatar_uid':'16','window_sha256':window},'lease_evidence')
        self.lease={'schema':'native-surface-lease-v1','lease_id':'unit-lease','cell_id':'odoo-community',
            'account_sha256':'a'*64,'workspace_sha256':'b'*64,'window_sha256':window,'owner_sha256':'d'*64,
            'issued_at':started,'expires_at':expires,'evidence':proof}
    def owns(self,page,meta):
        return (page is self.page and page.url.startswith('http://127.0.0.1:8078/odoo') and
            meta['account_uid']=='16' and meta['visible'] and meta['top_window'] and meta['app_shell'])
    def check(self,bound):
        reference=self.store.json(f'unit-check-{self.n}.private.json',{'fixture_only':True,'active':self.active},'lease_check');self.n+=1
        return {'schema':'native-surface-lease-check-v1','lease_sha256':policy.digest(bound),
            'status':'active' if self.active else 'inactive','checked_at':time.monotonic(),
            'expires_at':self.lease['expires_at'],'evidence':reference}


class Page:
    viewport_size={'width':1440,'height':1000}
    def __init__(self):
        self.url='http://127.0.0.1:8078/odoo/purchase/42';self.raw=image();self.calls=[];self.uncertain=False
        self.meta={'schema':'odoo-current-native-surface-v6','visible':True,'top_window':True,'app_shell':True,
            'account_uid':'16','route_path':'/odoo/purchase/42','viewport':[1440,1000],
            'focus':{'ref':'price','tag':'input','type':'text','name':'price_unit','editable':True,'bounds':[780,400,60,40],'value':'10'},
            'modals':[],'targets':[{'ref':'price','bounds':[780,400,60,40],'visible':True,'enabled':True,'obscured':False,'keyboard':True,
                'actions':['click','double_click','type','key','scroll','drag'],'tag':'input','type':'text','name':'price_unit','value':'10'},
                {'ref':'save','bounds':[100,20,60,30],'visible':True,'enabled':True,'obscured':False,'keyboard':False,
                 'actions':['click','double_click','scroll','drag'],'tag':'button','type':'button','name':'','value':None}], 'hits':[]}
        self.mouse=SimpleNamespace(click=self.click,dblclick=self.click,move=self.click,down=self.click,up=self.click)
        self.keyboard=SimpleNamespace(press=self.key,insert_text=self.key)
    def click(self,*args,**kwargs):
        self.calls.append(('click',args))
        if self.uncertain:raise OSError('fixture-driver-uncertain')
    def key(self,*args,**kwargs):self.calls.append(('key',args))
    def wait_for_timeout(self,duration):self.calls.append(('wait',duration))
    def screenshot(self,**kwargs):return self.raw
    def locator(self,selector):
        return SimpleNamespace(count=lambda:1,is_visible=lambda:True,is_enabled=lambda:True,
            bounding_box=lambda:{'x':780,'y':400,'width':60,'height':40})
    def evaluate(self,script,args=None):
        if script==adapter.VISIBLE_CONTROLS_JS:
            return [{'ref':'price','role':'input','label':'Price','visible':True,'enabled':True},
                    {'ref':'save','role':'button','label':'Save','visible':True,'enabled':True}]
        if script==adapter.NATIVE_CONTEXT_JS:
            meta=copy.deepcopy(self.meta)
            for i,point in enumerate(args or []):
                target=next((row for row in meta['targets'] if row['bounds'][0]<=point['x']<row['bounds'][0]+row['bounds'][2] and row['bounds'][1]<=point['y']<row['bounds'][1]+row['bounds'][3]),None)
                meta['hits'].append({'ref':f'point-{i}','bounds':[point['x'],point['y'],1,1],
                    'visible':True,'enabled':target['enabled'] if target else True,'obscured':target['obscured'] if target else False,
                    'keyboard':target['keyboard'] if target else False,'actions':target['actions'] if target else ['click','double_click','scroll','drag']})
            return meta
        raise AssertionError('unexpected fixture JS')


class SurfaceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.page=Page();self.a=adapter.OdooV066NativeSurfaceAdapter(self.page,task_id='opaque-train',task_binding_sha256='a'*64,instruction='Edit the owned document')
        self.boundary_patch=patch.object(adapter,'OdooLeaseEvidence',Boundary);self.boundary_patch.start()
        self.a.bind_guard(self.root,self.root)
    def tearDown(self):self.boundary_patch.stop();self.tmp.cleanup()
    def action(self,kind='click',**kwargs):
        return self.a.parse_current_action(json.dumps({'type':kind,**kwargs}))
    def audit(self,result,observation):
        return adapter.audit_guard(result['public_contract_receipt']['native_surface_guard'],
            observation.screenshot_bytes,lambda ref:read_ref(self.root,ref),action=result['action'])

    def test_raster_and_task_value_changes_permitted_with_full_native_evidence(self):
        observation,_=self.a.observe_for_model();action=self.action(target={'x':810,'y':420})
        self.page.raw=image()+b'fixture-trailing-png-data';self.page.meta['focus']['value']='unrelated changed displayed value'
        result=self.a.dispatch(action)
        self.assertEqual(result['status'],'applied');self.assertEqual(len(self.page.calls),1)
        audited=self.audit(result,observation);self.assertEqual(audited['raw_predispatch_images_reopened'],1)
        capsule=json.loads(read_ref(self.root,result['public_contract_receipt']['native_surface_guard']))
        self.assertNotEqual(capsule['observed']['raw_image']['sha256'],capsule['current']['raw_image']['sha256'])

    def test_recoverable_modal_rejection_consumes_turn_nonce_and_exposes_truthful_feedback(self):
        observation,_=self.a.observe_for_model();action=self.action('key',key='Enter')
        self.page.meta['modals']=[{'tag':'div','role':'dialog','class_name':'modal','bounds':[100,100,200,100]}]
        rejected=self.a.dispatch(action)
        self.assertEqual(rejected['status'],'rejected');self.assertEqual(self.page.calls,[])
        self.assertEqual(self.a.step,1);self.assertIsNone(self.a.latest)
        self.assertEqual(self.audit(rejected,observation)['dispatch_status'],'rejected')
        fresh,rendered=self.a.observe_for_model();self.assertNotEqual(fresh.frame_id,observation.frame_id)
        self.assertEqual(fresh.previous_action_result['status'],'rejected')
        self.assertNotIn('applied',json.dumps(fresh.previous_action_result))
        with self.assertRaises(ContractError):self.a.parse_current_action(action)

    def test_wrong_account_outside_origin_or_lost_lease_hard_stop_without_driver(self):
        for change in ('account','url','lease'):
            with self.subTest(change=change):
                self.tearDown();self.setUp();self.a.observe_for_model();action=self.action(target={'x':810,'y':420})
                if change=='account':self.page.meta['account_uid']='999'
                elif change=='url':self.page.url='https://outside.invalid/odoo'
                else:self.a.boundary.active=False
                with self.assertRaises(adapter.GuardHardStop):self.a.dispatch(action)
                self.assertEqual(self.page.calls,[])
                self.assertTrue(list(self.root.glob('surface-guard/turn-000/*predispatch*')))
                self.assertTrue(list(self.root.glob('surface-guard/turn-000/receipt.private.json')))

    def test_current_disabled_obscured_target_and_focus_change_rejected(self):
        for change in ('disabled','obscured','focus','viewport'):
            self.tearDown();self.setUp();self.a.observe_for_model();action=self.action('key',key='Enter') if change=='focus' else self.action(target={'x':810,'y':420})
            if change=='disabled':self.page.meta['targets'][0]['enabled']=False
            elif change=='obscured':self.page.meta['targets'][0]['obscured']=True
            elif change=='focus':self.page.meta['focus']['ref']='save'
            else:self.page.meta['viewport']=[1440,900]
            if change=='viewport':
                with self.assertRaises(adapter.GuardHardStop):self.a.dispatch(action)
            else:self.assertEqual(self.a.dispatch(action)['status'],'rejected')
            self.assertEqual(self.page.calls,[])

    def test_expired_observation_rejected_after_retaining_native_evidence(self):
        observation,_=self.a.observe_for_model();action=self.action(target={'x':810,'y':420})
        future=observation.expires_at+.1;self.a.clock=lambda:future
        with patch.object(time,'monotonic',return_value=future):result=self.a.dispatch(action)
        self.assertEqual(result['status'],'rejected');self.assertEqual(result['code'],'expired_observation')
        self.assertEqual(self.page.calls,[]);self.assertTrue((self.root/'surface-guard/turn-000/predispatch.png').is_file())

    def test_uncertain_native_io_quarantines_without_applied_receipt_or_replay(self):
        self.a.observe_for_model();action=self.action(target={'x':810,'y':420});self.page.uncertain=True
        with self.assertRaises(adapter.GuardDriverUncertain):self.a.dispatch(action)
        self.assertEqual(len(self.page.calls),1)
        capsule=json.loads((self.root/'surface-guard/turn-000/receipt.private.json').read_bytes())
        self.assertEqual(capsule['receipt']['status'],'failed');self.assertEqual(capsule['receipt']['driver_result'],'unknown')
        with self.assertRaises(adapter.GuardHardStop):self.a.dispatch(action)
        self.assertEqual(len(self.page.calls),1)

    def test_logical_finish_is_not_labeled_native_io_applied(self):
        observation,_=self.a.observe_for_model();result=self.a.dispatch(self.action('finish'))
        self.assertEqual(result['status'],'finished');self.assertTrue(result['finished']);self.assertEqual(self.page.calls,[])
        self.assertEqual(self.audit(result,observation)['dispatch_status'],'finished')

    def test_safe_wrong_object_action_is_permitted_and_independent_target_check_fails(self):
        self.a.observe_for_model();result=self.a.dispatch(self.action(target={'x':120,'y':35}))
        self.assertEqual(result['status'],'applied');self.assertEqual(len(self.page.calls),1)
        # Independent fixture goal is editing the price, not merely clicking
        # Save. No target/value answer is supplied to the safety guard.
        independent_goal_pass=any(kind=='key' for kind,args in self.page.calls)
        self.assertFalse(independent_goal_pass)

    def test_post_target_click_focus_loss_blocks_keyboard_and_retains_partial_failure(self):
        self.a.observe_for_model();action=self.action('type',target={'ref':'price'},text='100',mode='fill')
        original=self.page.mouse.click
        def lose_focus(*args,**kwargs):
            original(*args,**kwargs);self.page.meta['focus']['editable']=False
        self.page.mouse.click=lose_focus
        with self.assertRaises(adapter.GuardHardStop):self.a.dispatch(action)
        self.assertEqual([kind for kind,args in self.page.calls],['click'])
        capsule=json.loads((self.root/'surface-guard/turn-000/receipt.private.json').read_bytes())
        self.assertEqual(capsule['receipt']['status'],'failed')
        self.assertEqual(capsule['receipt']['driver_result'],'failed')

    def test_forged_capsule_cannot_replace_native_target_or_driver_return_evidence(self):
        observation,_=self.a.observe_for_model();result=self.a.dispatch(self.action(target={'x':810,'y':420}))
        capsule=json.loads(read_ref(self.root,result['public_contract_receipt']['native_surface_guard']))
        capsule['current']['targets'][1]['enabled']=False
        ref=self.a.store.json('forged-capsule.private.json',capsule,'dispatch_receipt')
        with self.assertRaisesRegex(policy.GuardError,'guard_native_envelope_not_rederived'):
            adapter.audit_guard(ref,observation.screenshot_bytes,lambda r:read_ref(self.root,r),action=result['action'])
        original=json.loads(read_ref(self.root,result['public_contract_receipt']['native_surface_guard']))
        driver=json.loads(read_ref(self.root,original['receipt']['driver_evidence']))
        returned=driver['calls'][0]['completion'];path=self.root/returned['path']
        path.write_text('{}');path.chmod(0o600)
        with self.assertRaises(policy.GuardError):self.audit(result,observation)

    @unittest.skipUnless(os.environ.get('ODOO_SURFACE_V6_ACTUAL_ROOT'),'Saved native roots not supplied')
    def test_actual_v3_and_v4_raster_pairs_are_seen_unmodified_and_pass_same_safety_policy(self):
        base=Path(os.environ['ODOO_SURFACE_V6_ACTUAL_ROOT'])
        pairs=[('v3','frames/step-009.png','frames/guard-0057.png','4968d5e427e4b86efd960e4f4edadccabd51eafeadb4a0706ad2bafd0221266e'),
               ('v4','frames/step-001.png','frames/guard-0007.png','8f610aa6f9b3d0fa93e7c0e75a516125a745690bdd1a7c2767e5fb24410d24e0')]
        for label,first,second,expected in pairs:
            self.tearDown();self.setUp();self.page.raw=(base/label/first).read_bytes()
            self.assertEqual(sha256(self.page.raw).hexdigest(),expected)
            observation,_=self.a.observe_for_model();action=self.action('key',key='Enter')
            self.page.raw=(base/label/second).read_bytes()
            result=self.a.dispatch(action);self.assertEqual(result['status'],'applied')
            capsule=json.loads(read_ref(self.root,result['public_contract_receipt']['native_surface_guard']))
            self.assertEqual(read_ref(self.root,capsule['current']['raw_image']),self.page.raw)
            self.assertEqual(self.audit(result,observation)['raw_observation_images_reopened'],1)
        # The retained pixels are actual evidence; current ownership metadata
        # above is explicitly a unit fixture, not retrospective native proof.


if __name__=='__main__':unittest.main()
