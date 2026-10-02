"""Production DOM focus metadata and real guard IO on synthetic Chromium only."""
from contextlib import contextmanager
from pathlib import Path
import json,tempfile,time,unittest
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from cursibench import native_surface_guard_policy_v1 as policy
from enterprise_fallback.odoo18 import odoo_v066_native_surface_adapter_v13 as native
from enterprise_fallback.odoo18 import native_surface_workers_v13 as workers
import factory,worker_lease

HTML='''<style>body{margin:0}.o_main_navbar{height:46px;background:#ddd}.o_user_menu{position:absolute;right:0;top:0}button{display:block;width:100px;height:3px}#focused{position:absolute;left:754px;top:474px;width:93px;height:22px}</style>
<div class="o_web_client o_action"><div class="o_main_navbar"><div class="o_user_menu"><img class="o_user_avatar" src="/web/image/res.partner/17/avatar_128" style="width:28px;height:28px"></div></div><div id="controls"></div><input id="focused" type="text" value="76.00"></div>
<div id="foreign" style="position:absolute;left:1000px;top:300px"><input id="outside" type="text" value="outside"></div>'''


class NativeFocusTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=sync_playwright().start();cls.browser=cls.p.chromium.launch(headless=True)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop()
 def setUp(self):
  self.page=self.browser.new_page(viewport=native.VIEWPORT)
  self.page.route('**/*',lambda r:r.fulfill(body='<html></html>',content_type='text/html'))
  self.page.goto('http://127.0.0.1:8069/odoo/replenishment')
  self.page.set_content(HTML)
  self.page.locator('#controls').evaluate('(e)=>{for(let i=0;i<180;i++){let b=document.createElement("button");b.textContent="Unrelated control "+i;e.appendChild(b)}}')
  self.page.locator('.o_user_avatar').evaluate('(e)=>{const c=document.createElement("canvas");c.width=28;c.height=28;e.src=c.toDataURL()}')
  # Principal witness uses a current native image URL; the intercepted PNG
  # need not disclose credentials or access a live Odoo route.
  self.page.route('**/avatar_128',lambda r:r.fulfill(body=bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c636000020000050001a5f645400000000049454e44ae426082'),content_type='image/png'))
  self.page.locator('.o_user_avatar').evaluate('(e)=>e.src="/web/image/res.partner/17/avatar_128"')
  self.page.wait_for_function('document.querySelector(".o_user_avatar").complete && document.querySelector(".o_user_avatar").naturalWidth>0')
 def tearDown(self):self.page.close()
 def capture(self):
  controls=self.page.evaluate(native.VISIBLE_CONTROLS_JS);meta=self.page.evaluate(native.NATIVE_CONTEXT_JS,[]);return controls,meta
 def test_actual_focus_beyond_cap_has_unique_stable_reference_in_both_target_sets(self):
  self.page.locator('#focused').focus();controls,observed=self.capture();current=self.page.evaluate(native.NATIVE_CONTEXT_JS,[])
  ref=observed['focus']['ref'];self.assertTrue(ref.startswith('nf'));self.assertNotEqual(ref,'body');self.assertEqual(ref,current['focus']['ref'])
  self.assertLessEqual(len(controls),128);self.assertTrue(any(c['ref']==ref for c in controls))
  for meta in [observed,current]:
   target=next(t for t in meta['targets'] if t['ref']==ref)
   self.assertTrue(target['keyboard']);self.assertTrue(target['enabled']);self.assertEqual(target['bounds'],meta['focus']['bounds'])
   rows=native.OdooV066NativeSurfaceAdapter._targets(None,meta,{'type':'key','key':'Meta+A'})
   self.assertTrue(next(t for t in rows if t['ref']==ref)['keyboard'])
   self.assertFalse(any(t['keyboard'] for t in rows if t['ref'] in ['body','workspace']))
  self.page.evaluate(native.VISIBLE_CONTROLS_JS);fresh=self.page.evaluate(native.NATIVE_CONTEXT_JS,[]);self.assertEqual(ref,fresh['focus']['ref'])
 def test_contenteditable_outside_generic_selector_retained_by_native_focus_witness(self):
  self.page.locator('.o_web_client').evaluate('(e)=>e.insertAdjacentHTML("beforeend",\'<div id="editor" contenteditable="true" style="position:absolute;left:500px;top:500px;width:120px;height:40px">Editable</div>\')')
  self.page.locator('#editor').focus();_,meta=self.capture();ref=meta['focus']['ref']
  self.assertTrue(meta['focused_target']['keyboard']);self.assertTrue(any(t['ref']==ref for t in meta['targets']))
 def test_readonly_disabled_and_foreign_focus_remain_unsafe(self):
  self.page.locator('#focused').evaluate('(e)=>e.readOnly=true');self.page.locator('#focused').focus();_,meta=self.capture()
  self.assertFalse(meta['focused_target']['keyboard'])
  self.page.locator('#focused').evaluate('(e)=>{e.readOnly=false;e.parentElement.setAttribute("aria-disabled","true")}')
  _,meta=self.capture();self.assertFalse(meta['focused_target']['enabled']);self.assertFalse(meta['focused_target']['keyboard'])
  self.page.locator('.o_web_client').evaluate('(e)=>e.removeAttribute("aria-disabled")');self.page.locator('#outside').focus();_,meta=self.capture()
  self.assertFalse(meta['focus_owned_app']);self.assertFalse(meta['focused_target']['enabled'])
 def test_body_and_canvas_never_gain_keyboard_fallback(self):
  self.page.locator('body').evaluate('(e)=>e.insertAdjacentHTML("beforeend",\'<canvas id="canvas" tabindex="0" width="100" height="100"></canvas>\')')
  self.page.locator('#canvas').focus();_,meta=self.capture();self.assertFalse(meta['focused_target']['keyboard'])
  self.page.locator('#canvas').evaluate('(e)=>e.blur()');_,meta=self.capture();rows=native.OdooV066NativeSurfaceAdapter._targets(None,meta)
  self.assertFalse(any(t['keyboard'] for t in rows if t['ref'] in ['body','workspace']))
 @contextmanager
 def actual_guard(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);private=root/'private';artifacts=root/'artifacts';private.mkdir(mode=0o700);artifacts.mkdir(mode=0o700)
   credentials=private/'actor_credentials.json';credentials.write_text('{"login":"synthetic","password":"fixture"}');credentials.chmod(0o600)
   with patch.object(factory,'PRIVATE',private),patch.object(worker_lease,'PRIVATE',private),patch.object(factory,'local_config',return_value={'ODOO_PORT':'8069','ODOO_PROJECT':'fixture'}):
    with worker_lease.exclusive_worker_operation('source_fixture',root=private):
     adapter=native.OdooV066NativeSurfaceAdapter(self.page,task_id='focus-fixture',task_binding_sha256='a'*64,instruction='Synthetic focus fixture')
     adapter.bind_guard(root=artifacts,worker_private=private);yield adapter,artifacts
 def test_actual_current_guard_meta_a_applies_once_and_reopens_driver_receipt(self):
  self.page.locator('#focused').focus()
  with self.actual_guard() as (adapter,root):
   observation,_=adapter.observe_for_model();action=adapter.parse_current_action('{"type":"key","key":"Meta+A"}')
   result=adapter.dispatch(action);self.assertEqual(result['status'],'applied')
   capsule=json.loads(workers.native_ref_bytes(root,result['public_contract_receipt']['native_surface_guard']))
   self.assertEqual(capsule['observed']['focus_id'],capsule['current']['focus_id']);self.assertTrue(capsule['observed']['focus_id'].startswith('nf'))
   self.assertEqual(capsule['receipt']['driver_result'],'succeeded')
   driver=json.loads(workers.native_ref_bytes(root,capsule['receipt']['driver_evidence']))
   self.assertEqual([c['operation'] for c in driver['calls']],['press'])
   with self.assertRaises(Exception):adapter.dispatch(action)
   audited=workers.audit_native_contract(result['public_contract_receipt'],action,observation.screenshot_bytes,0,
    {'task_id':'focus-fixture','package_sha256':'a'*64},root,observation_control_refs=sorted(c.ref for c in observation.controls if c.visible and c.enabled))
   self.assertEqual(audited['dispatch_status'],'applied')
 def test_current_focus_change_rejects_without_keyboard_io(self):
  self.page.locator('#focused').focus()
  with self.actual_guard() as (adapter,root):
   observation,_=adapter.observe_for_model()
   self.page.locator('.o_web_client').evaluate('(e)=>e.insertAdjacentHTML("beforeend",\'<input id="second" style="position:absolute;left:500px;top:400px;width:100px;height:30px">\')')
   self.page.locator('#second').focus()
   result=adapter.dispatch('{"type":"key","key":"Meta+A"}')
   self.assertEqual(result['status'],'rejected')
   capsule=json.loads(workers.native_ref_bytes(root,result['public_contract_receipt']['native_surface_guard']))
   self.assertNotEqual(capsule['observed']['focus_id'],capsule['current']['focus_id'])
   self.assertIsNone(capsule['receipt']['intent']);self.assertEqual(capsule['receipt']['driver_result'],'not_attempted')
 def test_actual_guard_rejects_noneditable_or_foreign_focus_without_io(self):
  for selector,readonly in [('#focused',True),('#outside',False)]:
   with self.subTest(selector=selector):
    self.page.locator('#focused').evaluate('(e)=>e.readOnly=false')
    if readonly:self.page.locator(selector).evaluate('(e)=>e.readOnly=true')
    self.page.locator(selector).focus()
    with self.actual_guard() as (adapter,root):
     observation,_=adapter.observe_for_model();result=adapter.dispatch('{"type":"key","key":"Meta+A"}')
     self.assertEqual(result['status'],'rejected')
     capsule=json.loads(workers.native_ref_bytes(root,result['public_contract_receipt']['native_surface_guard']))
     self.assertIsNone(capsule['receipt']['intent']);self.assertEqual(capsule['receipt']['driver_result'],'not_attempted')

if __name__=='__main__':unittest.main()
