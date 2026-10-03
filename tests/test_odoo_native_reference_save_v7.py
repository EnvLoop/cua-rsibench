"""Local Chromium Ref7 boundaries only; no world or qualification credit.

The fixture journal is explicitly unguarded. The native indicator is real HTML
in Chromium; delayed onchange completion models a late form-dirty notification.
"""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from enterprise_fallback.odoo18 import native_reference_save_v7 as reference
from enterprise_fallback.odoo18.odoo_actor_clock_v1 import ActorClock
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from tests.test_odoo_native_reference_save_v5 import LocalRecipeJournal,form_html,list_html

FROZEN_REF6={
 'enterprise_fallback/odoo18/native_reference_save_v6.py':'b6154da8ce2f887026437fffa5dfd018851f77d86bc29bb2352b3f0f51d87993',
 'enterprise_fallback/odoo18/native_reference_viewport_v6.py':'a5774806ba6770c72c682b3ed68ad9b67036d6fbd51f11c0b082c10130e10b7e',
 'tools/odoo_v066_scale_recipes_v7.py':'8136a6eb764f4de2ca0a3fbb417f8d2058e006d3036dbed944f453de81afd96c',
 'tools/odoo_v066_native_reference_qualification_v6.py':'3f8a051b28460d7f20217aec52580e16814459e97cadfb25735b66c33901c9c9',
 'enterprise_fallback/odoo18/native_reference_split_finalizer_v6.py':'b8f2fcad5ca401f077c10f2eea8f3d58654e5ff732482bf1d95e3a997ff027b9',
 'tests/test_odoo_native_reference_save_v6.py':'cb9f2d46b51e2ccffd5af7b907f6fe3d6f5846c085023fc674a0dbce1574b886',
 'tests/test_odoo_native_reference_epoch_v6.py':'2d08aef3ea03290e46db6783439cc6205b22f3cb374fa6ccfd871938dd8b5e5a'}


class FixtureJournal(LocalRecipeJournal):
    def __init__(self):
        super().__init__();self.trace=[{'local_prior_action':0},{'local_prior_action':1}]
    def act(self,*args,**kwargs):
        value=super().act(*args,**kwargs);self.trace.append({'local_save_click':True});return value


class SaveV7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start();cls.browser=cls.playwright.chromium.launch(headless=True)
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.playwright.stop()
    def setUp(self):
        self.page=self.browser.new_page(viewport={'width':1440,'height':1000})
        self.page.route('**/*',lambda route:route.abort());self.journal=FixtureJournal()
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.journal.out=Path(self.directory.name)
    def tearDown(self):self.page.close()
    def saved_form(self):
        self.page.set_content(form_html());self.page.evaluate("document.querySelector('.o_form_status_indicator_buttons').classList.add('invisible')")
    def save(self,**options):
        return reference.save_original_form(self.page,self.journal,'fixture',timeout_seconds=options.get('timeout_seconds',.3),
            poll_seconds=options.get('poll_seconds',.005),stable_seconds=options.get('stable_seconds',.015))
    def no_input(self):
        self.assertEqual(self.journal.actions,[]);self.assertEqual(len(self.journal.trace),2)
        self.assertEqual(self.page.evaluate('window.clickCount'),0)
    def release_during_wait(self,change):
        actual=self.page.wait_for_timeout;released=[]
        def wait(milliseconds):
            if not released:
                released.append(True);self.page.evaluate(change)
            return actual(milliseconds)
        return patch.object(self.page,'wait_for_timeout',side_effect=wait)

    def test_async_customer_reference_onchange_reclassifies_before_intent_then_saves_once(self):
        self.saved_form()
        self.page.evaluate("""document.body.insertAdjacentHTML('beforeend',
            '<input aria-label="Customer reference" onchange="window.pendingDirtyChange=true">'+
            '<button id="blur">Blur fixture input</button>')""")
        self.page.get_by_role('textbox',name='Customer reference').fill('Updated local reference')
        self.page.locator('#blur').click();self.assertTrue(self.page.evaluate('window.pendingDirtyChange'))
        change="""if(window.pendingDirtyChange){setTimeout(()=>{
            document.querySelector('.o_form_status_indicator_buttons').classList.remove('invisible');
            window.pendingDirtyChange=false;},0)}"""
        with self.release_during_wait(change):proof=self.save()
        self.assertEqual(proof['status'],'saved_native_indicator');self.assertTrue(proof['one_native_save_click'])
        self.assertEqual(len(self.journal.actions),1);self.assertEqual(self.page.evaluate('window.clickCount'),1)
        readiness=json.loads((self.journal.out/'reference-save-002-readiness.private.json').read_bytes())
        self.assertEqual(readiness['initial_native_indicator']['mode'],'saved')
        self.assertEqual(readiness['reclassified_native_indicator']['mode'],'dirty')
        self.assertEqual((readiness['actor_action_count_before'],readiness['actor_action_count_after']),(2,2))
        self.assertTrue(readiness['no_save_or_other_gui_input_performed']);self.assertFalse(readiness['same_action_retry_performed'])
        intents=list(self.journal.out.glob('*-intent.private.json'));self.assertEqual(len(intents),1)
        self.assertTrue(json.loads(intents[0].read_bytes())['one_guarded_click_required'])

    def test_toolbar_becoming_dirty_between_read_only_samples_is_positively_reopened(self):
        self.saved_form();actual=self.page.get_by_role;changed=[]
        def role(*args,**kwargs):
            if args==('button',) and kwargs.get('name')=='Save manually' and not changed:
                changed.append(True);self.page.evaluate("document.querySelector('.o_form_status_indicator_buttons').classList.remove('invisible')")
            return actual(*args,**kwargs)
        with patch.object(self.page,'get_by_role',side_effect=role):proof=self.save()
        self.assertEqual(proof['status'],'saved_native_indicator');self.assertEqual(len(self.journal.actions),1)
        self.assertEqual(self.page.evaluate('window.clickCount'),1)

    def test_stable_saved_form_and_list_have_zero_input_and_unchanged_action_count(self):
        for kind in ('form','list'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                self.journal=FixtureJournal();self.journal.out=Path(directory)
                if kind=='form':self.saved_form()
                else:
                    self.page.set_content(list_html());self.page.evaluate("document.querySelectorAll('.o_list_button_save,.o_list_button_discard').forEach(element=>element.remove())")
                proof=self.save();self.assertEqual(proof['status'],'already_saved_native_indicator');self.no_input()
                self.assertFalse(proof['one_native_save_click']);self.assertEqual(proof['actor_action_count_before'],proof['actor_action_count_after'])
                self.assertFalse(list(self.journal.out.glob('*-readiness.private.json')))

    def test_initial_dirty_original_form_still_requires_one_commit_click(self):
        self.page.set_content(form_html());proof=self.save()
        self.assertEqual(proof['status'],'saved_native_indicator');self.assertEqual(len(self.journal.actions),1)
        self.assertEqual(self.page.evaluate('window.clickCount'),1)

    def test_saved_to_invalid_or_foreign_document_before_input_refuses_without_intent(self):
        for kind,change in [('invalid',"document.querySelector('.o_form_status_indicator').insertAdjacentHTML('beforeend','<span class=\"text-danger\">Invalid fixture</span>')"),
                            ('foreign',"location.hash='different-current-document'")]:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                self.journal=FixtureJournal();self.journal.out=Path(directory);self.saved_form()
                with self.release_during_wait(change):
                    with self.assertRaises(RuntimeError):self.save()
                self.no_input();self.assertFalse(list(self.journal.out.glob('*-intent.private.json')))

    def test_saved_indicator_with_visible_save_and_still_saved_reread_refuses(self):
        self.saved_form();self.page.evaluate("document.body.insertAdjacentHTML('beforeend','<button>Save</button>')")
        with self.assertRaisesRegex(RuntimeError,'disagrees_with_visible_save'):self.save()
        self.no_input()

    def test_post_click_invalid_foreign_or_dirty_timeout_never_clicks_again(self):
        changes={'invalid':"document.querySelector('.o_form_status_indicator').insertAdjacentHTML('beforeend','<span class=\"text-danger\">Invalid fixture</span>')",
                 'foreign':"location.hash='changed-after-save'",'dirty':"document.querySelector('.o_form_status_indicator_buttons').classList.remove('invisible')"}
        for kind,change in changes.items():
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                self.journal=FixtureJournal();self.journal.out=Path(directory);self.page.set_content(form_html())
                self.journal.after_click=lambda change=change:self.page.evaluate(change)
                with self.assertRaises(RuntimeError):self.save(timeout_seconds=.04,stable_seconds=.005)
                self.assertEqual(len(self.journal.actions),1);self.assertEqual(self.page.evaluate('window.clickCount'),1)
                self.assertFalse(list(self.journal.out.glob('*-result.private.json')))

    def test_guard_exception_propagates_without_dispatch_retry(self):
        self.page.set_content(form_html());error=RuntimeError('fixture guard rejected')
        self.journal.error=error
        with self.assertRaises(RuntimeError) as caught:self.save()
        self.assertIs(caught.exception,error);self.assertEqual(len(self.journal.actions),1)
        self.assertEqual(self.page.evaluate('window.clickCount'),0)

    def test_actual_actor_deadline_before_and_after_single_click_has_no_retry(self):
        for when in ('before','after'):
            with self.subTest(when=when),tempfile.TemporaryDirectory() as directory:
                self.journal=FixtureJournal();self.journal.out=Path(directory);self.page.set_content(form_html())
                tick=[720 if when=='before' else 0]
                self.journal.adapter.actor_clock=ActorClock(task_id='local-ref7-fixture',package_sha256='a'*64,started=0,clock=lambda:tick[0])
                if when=='after':self.journal.after_click=lambda:tick.__setitem__(0,720)
                with self.assertRaises(ActorDeadlineReached):self.save()
                self.assertEqual(len(self.journal.actions),0 if when=='before' else 1)
                self.assertEqual(self.page.evaluate('window.clickCount'),0 if when=='before' else 1)

    def test_deadline_during_pre_click_saved_stabilization_stops_without_input(self):
        self.saved_form();tick=[0];self.journal.adapter.actor_clock=ActorClock(task_id='local-ref7-fixture',package_sha256='a'*64,started=0,clock=lambda:tick[0])
        actual=self.page.wait_for_timeout
        def wait(milliseconds):
            value=actual(milliseconds);tick[0]=720;return value
        with patch.object(self.page,'wait_for_timeout',side_effect=wait):
            with self.assertRaises(ActorDeadlineReached):self.save()
        self.no_input();self.assertFalse(list(self.journal.out.glob('*-intent.private.json')))

    def test_frozen_ref6_seven_source_and_test_files_remain_exact(self):
        root=Path(__file__).resolve().parents[1]
        for name,digest in FROZEN_REF6.items():
            with self.subTest(file=name):self.assertEqual(sha256((root/name).read_bytes()).hexdigest(),digest)


if __name__=='__main__':unittest.main()
