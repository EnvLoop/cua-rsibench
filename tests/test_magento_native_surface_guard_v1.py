"""Production async guard/native IO; synthetic native page and lease only."""
import asyncio
import copy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
from cursibench import native_surface_guard_policy_v1 as policy
from magento_catalog_factory.native_surface_guard_v1 import NativeAdapter,NATIVE_JS,GuardHardStop


class Page:
    def __init__(self):
        self.tick=time.monotonic();self.calls=[];self.url='http://127.0.0.1:7820/admin/catalog/product/index/'
        self.uid='synthetic-admin';self.modal=False;self.enabled=True;self.focus='body';self.busy=False;self.capture=0
        async def click(x,y):self.calls.append(('click',x,y));self.focus='price'
        async def press(key):self.calls.append(('press',key))
        async def insert(text):self.calls.append(('insert',text))
        self.mouse=SimpleNamespace(click=click,dblclick=click,wheel=click,move=click,down=lambda:None,up=lambda:None)
        self.keyboard=SimpleNamespace(press=press,insert_text=insert)
    async def wait_for_timeout(self,duration):self.tick+=duration/1000
    async def screenshot(self,**kwargs):
        image=Image.new('RGB',(1440,1000),'white');image.putpixel((1000,900),(self.capture%255,1,2));self.capture+=1
        out=BytesIO();image.save(out,'PNG');return out.getvalue()
    async def evaluate(self,script,points):
        if script!=NATIVE_JS:raise AssertionError('only actual native context getter allowed')
        target={'ref':'price','bounds':[20,30,200,40],'visible':True,'enabled':self.enabled,'obscured':False,
            'keyboard':True,'actions':['click','double_click','type','key','scroll','drag'],'role':'textbox','label':'Price'}
        return {'schema':'magento-native-context-v1','physical_url':self.url,'viewport':[1440,1000],
            'visible':True,'top_window':True,'app_shell':True,'native_username':self.uid,
            'account_witness':{'visible_count':1,'username':self.uid},'focus':{'ref':self.focus,'editable':self.focus=='price'},
            'modals':[{'bounds':[0,0,300,100]}] if self.modal else [],'targets':[target],'outside_modal_targets':[],
            'hits':[{**target,'ref':'point-'+str(i),'bounds':[p['x'],p['y'],1,1]} for i,p in enumerate(points)],
            'busy':[{}] if self.busy else [],'document_ready':True}


class Boundary:
    def __init__(self,page,store):
        self.page=page;self.active=True;self.count=0;self.store=store
        ref=store.json('fixture-lease.private.json',{'source_fixture_only':True},'lease_evidence')
        self.lease={'schema':'native-surface-lease-v1','lease_id':'fixture-owned-clone','cell_id':'magento-admin',
            'account_sha256':'a'*64,'workspace_sha256':'b'*64,'window_sha256':'c'*64,'owner_sha256':'d'*64,
            'issued_at':page.tick,'expires_at':page.tick+720,'evidence':ref}
    async def owns(self,page,meta):return page is self.page and meta['native_username']=='synthetic-admin' and meta['physical_url'].startswith('http://127.0.0.1:7820/admin')
    async def check(self,store):
        ref=store.json(f'fixture-check-{self.count}.private.json',{'active':self.active},'lease_check');self.count+=1
        return {'schema':'native-surface-lease-check-v1','lease_sha256':policy.digest(self.lease),
            'status':'active' if self.active else 'inactive','checked_at':self.page.tick,'expires_at':self.lease['expires_at'],'evidence':ref}


class NativeGuardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from enterprise_fallback.odoo18.odoo_native_surface_evidence_v6 import EvidenceStore
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700);self.page=Page();store=EvidenceStore(self.root)
        self.boundary=Boundary(self.page,store)
        self.adapter=NativeAdapter(page=self.page,task_id='synthetic-owned-task',package_sha256='e'*64,
            instruction='Repair the visible synthetic price',root=self.root,lease_boundary=self.boundary)
        self.adapter.clock=lambda:self.page.tick
        asyncio.get_running_loop().set_debug(False)
        self.timer=patch('time.monotonic',lambda:self.page.tick);self.timer.start();self.addCleanup(self.timer.stop)

    async def test_changed_raster_same_owned_native_target_applies_actual_io(self):
        observed,_=await self.adapter.observe()
        result=await self.adapter.dispatch('{"type":"click","target":{"x":50,"y":50}}')
        self.assertEqual(result['status'],'applied');self.assertEqual(self.page.calls,[('click',50,50)])
        capsule=json.loads((self.root/result['contract']['native_surface_guard']['path']).read_bytes())
        self.assertNotEqual(capsule['observed']['raw_image']['sha256'],capsule['current']['raw_image']['sha256'])
        self.assertEqual(capsule['receipt']['driver_result'],'succeeded')
        self.assertTrue(self.adapter.actor.events[0]['completion'])

    async def test_disabled_target_rejects_and_fresh_nonce_consumes_turn(self):
        observed,_=await self.adapter.observe();self.page.enabled=False
        result=await self.adapter.dispatch('{"type":"click","target":{"x":50,"y":50}}')
        self.assertEqual(result['status'],'rejected');self.assertEqual(self.page.calls,[])
        fresh,_=await self.adapter.observe();self.assertNotEqual(fresh.frame_id,observed.frame_id)
        self.assertEqual(fresh.previous_action_result['status'],'rejected');self.assertEqual(self.adapter.step,1)

    async def test_account_navigation_or_lease_loss_stops_before_io(self):
        await self.adapter.observe();self.page.uid='another-account'
        with self.assertRaises(GuardHardStop):await self.adapter.dispatch('{"type":"click","target":{"x":50,"y":50}}')
        self.assertEqual(self.page.calls,[])

    async def test_typed_absolute_deadline_has_no_gui(self):
        from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
        await self.adapter.observe();self.page.tick=self.adapter.actor.deadline
        with self.assertRaises(ActorDeadlineReached):await self.adapter.dispatch('{"type":"click","target":{"x":50,"y":50}}')
        self.assertEqual(self.page.calls,[])

    async def test_new_dialog_native_context_rejects_without_io(self):
        await self.adapter.observe();self.page.modal=True
        result=await self.adapter.dispatch('{"type":"click","target":{"x":50,"y":50}}')
        self.assertEqual(result['status'],'rejected');self.assertEqual(self.page.calls,[])
    async def test_expired_nonce_rejects_and_no_io(self):
        await self.adapter.observe();self.page.tick=self.adapter.latest.expires_at+.001
        result=await self.adapter.dispatch('{"type":"click","target":{"x":50,"y":50}}')
        self.assertEqual(result['status'],'rejected');self.assertEqual(self.page.calls,[])
    async def test_busy_timeout_durable_raw_and_no_gui(self):
        self.page.busy=True
        with self.assertRaisesRegex(GuardHardStop,'busy_timeout'):await self.adapter.observe()
        self.assertEqual(len(list(self.root.glob('guard/readiness-*.png'))),24);self.assertEqual(self.page.calls,[])
    async def test_uncertain_native_io_has_no_fake_applied_receipt_and_cannot_replay(self):
        async def unknown(*args):raise TimeoutError('synthetic uncertainty')
        self.page.mouse.click=unknown;await self.adapter.observe()
        with self.assertRaises(TimeoutError):await self.adapter.dispatch('{"type":"click","target":{"x":50,"y":50}}')
        self.assertTrue((self.root/'guard/turn-000/uncertain.private.json').is_file())
        self.assertFalse((self.root/'guard/turn-000/receipt.private.json').exists())
        with self.assertRaises(GuardHardStop):await self.adapter.observe()
    async def test_keyboard_focus_drift_rejects_without_typing(self):
        self.page.focus='price';await self.adapter.observe();self.page.focus='unknown-focus'
        result=await self.adapter.dispatch('{"type":"key","key":"Enter"}')
        self.assertEqual(result['status'],'rejected');self.assertEqual(self.page.calls,[])


if __name__=='__main__':unittest.main()
