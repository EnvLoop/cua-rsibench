"""Execute production role/context scripts in an isolated browser fixture.

These checks exercise native DOM hit testing, never benchmark qualification.
"""
import json
import os
from pathlib import Path
import unittest

from cursibench import native_surface_guard_policy_v1 as policy
from enterprise_fallback.odoo18 import native_surface_workers_v9 as workers
from enterprise_fallback.odoo18 import odoo_v066_native_surface_adapter_v9 as native


HTML = '''<!doctype html><html><body style="margin:0">
<div class="o_web_client o_action">
 <div class="o_main_navbar" style="height:46px;background:#555">
  <div class="o_user_menu" style="position:absolute;right:0;top:0">
   <button style="width:51px;height:46px">Account</button>
  </div>
 </div>
 <button id="background" style="position:absolute;left:20px;top:60px">Save</button>
 <div class="modal modal-fullscreen" style="position:absolute;inset:0">
  <div class="o-FileViewer" tabindex="0" style="position:absolute;inset:0;background:#777a">
   <div class="o-FileViewer-header" style="height:46px;background:#333">
    <div id="close" role="button" title="Close (Esc)" aria-label="Close"
     style="position:absolute;right:0;top:0;width:51px;height:46px">
     <i class="fa fa-times" style="display:block;width:51px;height:46px">X</i>
    </div>
   </div>
  </div>
 </div>
</div></body></html>'''


class NativeRoleControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport=native.VIEWPORT)
        self.page.set_content(HTML)

    def tearDown(self):
        self.page.close()

    def capture(self, points=None):
        controls = self.page.evaluate(native.VISIBLE_CONTROLS_JS)
        meta = self.page.evaluate(native.NATIVE_CONTEXT_JS, points or [])
        return controls, meta

    def test_role_div_close_is_observed_and_safe_at_actual_hit(self):
        controls, meta = self.capture([{"x": 1413, "y": 23}])
        ref = self.page.locator('#close').get_attribute('data-envloop-ref')
        self.assertTrue(any(row['ref'] == ref and row['role'] == 'button'
                            and row['label'] == 'Close' for row in controls))
        target = next(row for row in meta['targets'] if row['ref'] == ref)
        self.assertEqual(target['tag'], 'div')
        self.assertTrue(target['enabled'])
        self.assertFalse(target['obscured'])
        self.assertTrue(meta['hits'][0]['enabled'])
        self.assertEqual(len(meta['modals']), 1)
        self.assertIn('o-FileViewer', meta['modals'][0]['class_name'])

    def test_account_and_obscured_background_remain_unsafe(self):
        _, meta = self.capture()
        account_ref = self.page.locator('.o_user_menu button').get_attribute('data-envloop-ref')
        background_ref = self.page.locator('#background').get_attribute('data-envloop-ref')
        account = next(row for row in meta['targets'] if row['ref'] == account_ref)
        background = next(row for row in meta['targets'] if row['ref'] == background_ref)
        self.assertFalse(account['enabled'])
        self.assertTrue(account['obscured'])
        self.assertTrue(background['obscured'])

    def test_closed_viewer_has_no_stale_control_or_modal(self):
        self.capture()
        self.page.locator('.modal').evaluate('(el) => el.remove()')
        controls, meta = self.capture()
        self.assertFalse(any(row['label'] == 'Close' for row in controls))
        self.assertEqual(meta['modals'], [])
        account_ref = self.page.locator('.o_user_menu button').get_attribute('data-envloop-ref')
        account = next(row for row in meta['targets'] if row['ref'] == account_ref)
        self.assertFalse(account['enabled'])

    def test_generic_menu_option_and_attachment_coverage(self):
        self.page.locator('.modal').evaluate('(el) => el.remove()')
        self.page.locator('body').evaluate('''(el) => el.insertAdjacentHTML('beforeend',
            '<div role="menuitem" style="width:50px;height:30px">Menu</div>' +
            '<div role="option" style="width:50px;height:30px">Option</div>' +
            '<div class="o-mail-Attachment" style="width:50px;height:30px">Document</div>')''')
        controls, _ = self.capture()
        labels = {row['label'] for row in controls}
        self.assertTrue({'Menu', 'Option', 'Document'} <= labels)

    def test_same_binding_all_actor_paths_and_unchanged_limits(self):
        value = workers.public_binding()
        self.assertEqual(set(value['adapter_substitutions'].values()),
                         {'OdooV066NativeSurfaceAdapter'})
        self.assertEqual(value['native_surface_policy_sha256'], policy.POLICY_SHA)
        self.assertEqual(value['native_adapter_binding']['max_actions'], 90)
        self.assertEqual(value['native_adapter_binding']['wall_seconds'], 720)
        self.assertFalse(value['native_adapter_binding']['raster_equality_required'])

    def test_optional_saved_v8_rejection_remains_rejected(self):
        saved_root = os.environ.get('ENVLOOP_ODOO_V8_ROOT')
        if not saved_root:
            self.skipTest('Original private v8 run is not available')
        path = Path(saved_root) / 'attempt-000/surface-guard/turn-006/receipt.private.json'
        capsule = json.loads(path.read_bytes())
        decision = policy.decision(capsule['observed'], capsule['current'],
                                   capsule['action'],
                                   lease_check=lambda lease: capsule['decision']['lease_check'],
                                   now=capsule['audit_clock'])
        self.assertEqual(decision['status'], 'rejected')
        self.assertEqual(decision['reason'], 'target_not_current_and_safe')
        self.assertEqual(capsule['receipt']['driver_result'], 'not_attempted')


if __name__ == '__main__':
    unittest.main()
