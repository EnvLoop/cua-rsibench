"""Real local Chromium autosave wait boundaries; no native qualification.

The priority click is a local HTML fixture action performed before the helper.
The helper's journal prohibits every GUI action. No application/world/API runs.
"""
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from playwright.sync_api import sync_playwright
from enterprise_fallback.odoo18 import native_reference_autosave_v8 as reference
from enterprise_fallback.odoo18.odoo_actor_clock_v1 import ActorClock
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from tests.test_odoo_native_reference_save_v5 import LocalRecipeClock, form_html, list_html

FROZEN_REF7 = {
    'enterprise_fallback/odoo18/native_reference_save_v7.py': '047899419df2ac7313e2d96a1055aa00dce2146a5a849e351614da36bff47d96',
    'enterprise_fallback/odoo18/native_reference_viewport_v7.py': '80df9fbaed19984b905444737faeb4b8ee066e1c42793261a45fed9001f88461',
    'enterprise_fallback/odoo18/native_reference_split_finalizer_v7.py': '01443e6f78414d867c05054372144c5ef4e23f4ad0c9be4d287c74596b5996ff',
    'tools/odoo_v066_native_reference_qualification_v7.py': '416157786b358fa6eecac4358fb9745faf7e8bf50e142a4cb9354b385ee4a276',
    'tools/odoo_v066_scale_recipes_v8.py': '7df1dee3d911cd3813409501fc526f1675783f87a4eb2c2e91f04c2aeb5daa73',
    'tests/test_odoo_native_reference_save_v7.py': '9481f15b446a9b938e8f1c0c7c9960bc8cef87734a405b3768684acd0aa41fb3',
    'tests/test_odoo_native_reference_epoch_v7.py': '824c5b7782ffdd6ebacd1649c39b8793069f22323f8148fd944ab485b86b2007',
}


class NoInputJournal:
    def __init__(self, out):
        self.clock = LocalRecipeClock()
        self.adapter = SimpleNamespace(actor_clock=self.clock)
        self.trace = [{'local_prior_action': 0}, {'local_prior_priority_click': 1}]
        self.actions, self.out = [], Path(out)

    def act(self, *args, **kwargs):
        self.actions.append((args, kwargs))
        raise AssertionError('Autosave observation must never dispatch GUI input')


class AutosaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 1000})
        self.page.route('**/*', lambda route: route.abort())
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.journal = NoInputJournal(self.directory.name)

    def tearDown(self):
        self.page.close()

    def saved(self):
        self.page.set_content(form_html())
        self.page.evaluate("document.querySelector('.o_form_status_indicator_buttons').classList.add('invisible')")

    def fresh_journal(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.journal = NoInputJournal(directory.name)

    def wait(self, **options):
        return reference.wait_positive_priority_autosave(
            self.page, self.journal, 'local-priority-fixture',
            timeout_seconds=options.get('timeout_seconds', .6),
            poll_seconds=options.get('poll_seconds', .005),
            stable_seconds=options.get('stable_seconds', .02))

    def assert_no_input(self):
        self.assertEqual(self.journal.actions, [])
        self.assertEqual(self.page.evaluate('window.clickCount'), 0)

    def release_during_wait(self, change):
        actual = self.page.wait_for_timeout
        released = []
        def wait(milliseconds):
            if not released:
                released.append(True)
                self.page.evaluate(change)
            return actual(milliseconds)
        return patch.object(self.page, 'wait_for_timeout', side_effect=wait)

    def test_actual_priority_click_async_dirty_to_saved_waits_without_manual_save(self):
        self.saved()
        self.page.evaluate("""document.body.insertAdjacentHTML('beforeend',
            '<button id="priority">Priority fixture</button>');
            window.priorityClicks=0;
            document.querySelector('#priority').onclick=()=>{
                window.priorityClicks++;
                const buttons=document.querySelector('.o_form_status_indicator_buttons');
                buttons.classList.remove('invisible');
                setTimeout(()=>buttons.classList.add('invisible'),90);
            }; void 0;""")
        self.assertEqual(self.page.evaluate('window.priorityClicks'), 0)
        self.page.get_by_role('button', name='Priority fixture').click()
        proof = self.wait()
        self.assertEqual(self.page.evaluate('window.priorityClicks'), 1)
        self.assertEqual(len(self.journal.trace), 2)
        self.assertEqual(proof['status'], 'positive_current_priority_autosave_verified')
        self.assertTrue(any(sample['native']['mode'] == 'dirty' for sample in proof['samples']))
        self.assertEqual(proof['samples'][-1]['native']['mode'], 'saved')
        self.assertFalse(proof['gui_input_performed'])
        self.assertFalse(proof['same_action_retry_performed'])
        self.assertEqual((proof['actor_action_count_before'], proof['actor_action_count_after']), (2, 2))
        self.assertEqual(proof['trigger_action_step'], 1)
        self.assert_no_input()
        self.assertTrue(self.page.locator('.o_form_status_indicator_buttons').evaluate(
            "element=>element.classList.contains('invisible')"))

    def test_stable_saved_form_requires_read_only_stability(self):
        self.saved()
        self.assertTrue(self.wait())
        self.assert_no_input()
        self.assertEqual(len(self.journal.trace), 2)
        self.assertTrue(any('wait' in phase for phase in self.journal.clock.stages))

    def test_saved_window_restarts_after_new_dirty_notification_without_input(self):
        self.saved()
        actual = self.page.wait_for_timeout
        waits = []
        def wait(milliseconds):
            waits.append(milliseconds)
            if len(waits) == 1:
                self.page.evaluate("document.querySelector('.o_form_status_indicator_buttons').classList.remove('invisible')")
            elif len(waits) == 2:
                self.page.evaluate("document.querySelector('.o_form_status_indicator_buttons').classList.add('invisible')")
            return actual(milliseconds)
        with patch.object(self.page, 'wait_for_timeout', side_effect=wait):
            proof = self.wait(stable_seconds=.03)
        modes = [sample['native']['mode'] for sample in proof['samples']]
        self.assertEqual(modes[:3], ['saved', 'dirty', 'saved'])
        last_dirty = max(index for index, sample in enumerate(proof['samples']) if sample['native']['mode'] == 'dirty')
        first_saved = proof['samples'][last_dirty + 1]['monotonic']
        self.assertGreaterEqual(proof['samples'][-1]['monotonic'] - first_saved, .03)
        self.assertEqual(len(self.journal.trace), 2)
        self.assert_no_input()

    def test_invalid_duplicate_hidden_missing_or_css_ambiguous_indicator_refuses(self):
        changes = {
            'invalid': "document.querySelector('.o_form_status_indicator').insertAdjacentHTML('beforeend','<span class=\"text-danger\">Invalid local field</span>')",
            'duplicate root': "document.body.appendChild(document.querySelector('.o_form_status_indicator').cloneNode(true))",
            'hidden root': "document.querySelector('.o_form_status_indicator').hidden=true",
            'missing root': "document.querySelector('.o_form_status_indicator').remove()",
            'duplicate buttons': "document.querySelector('.o_form_status_indicator').appendChild(document.querySelector('.o_form_status_indicator_buttons').cloneNode(true))",
            'CSS disagreement': "document.querySelector('.o_form_status_indicator_buttons').style.visibility='visible'",
        }
        for label, change in changes.items():
            with self.subTest(case=label):
                self.fresh_journal()
                self.saved()
                self.page.evaluate(change)
                with self.assertRaises(RuntimeError):
                    self.wait(timeout_seconds=.08)
                self.assert_no_input()

    def test_list_saved_indicator_cannot_attest_priority_form_autosave(self):
        self.page.set_content(list_html())
        self.page.evaluate("document.querySelectorAll('.o_list_button_save,.o_list_button_discard').forEach(element=>element.remove())")
        with self.assertRaises(RuntimeError):
            self.wait(timeout_seconds=.08)
        self.assert_no_input()

    def test_saved_indicator_with_unrelated_visible_save_refuses(self):
        self.saved()
        self.page.evaluate("document.body.insertAdjacentHTML('beforeend','<button>Save</button>')")
        with self.assertRaises(RuntimeError):
            self.wait(timeout_seconds=.08)
        self.assert_no_input()

    def test_document_change_during_wait_refuses_zero_input(self):
        self.saved()
        with self.release_during_wait("location.hash='other-local-document'"):
            with self.assertRaises(RuntimeError):
                self.wait()
        self.assert_no_input()

    def test_invalid_indicator_appearing_during_stability_refuses(self):
        self.saved()
        change = "document.querySelector('.o_form_status_indicator').insertAdjacentHTML('beforeend','<span class=\"text-danger\">Invalid during autosave</span>')"
        with self.release_during_wait(change):
            with self.assertRaises(RuntimeError):
                self.wait()
        self.assert_no_input()

    def test_permanently_dirty_timeout_never_issues_save(self):
        self.page.set_content(form_html(saved_on_click=False))
        with self.assertRaises(RuntimeError):
            self.wait(timeout_seconds=.04, stable_seconds=.005)
        self.assert_no_input()

    def test_actor_deadline_before_read_and_after_wait_is_typed_and_zero_input(self):
        for when in ('before', 'after'):
            with self.subTest(when=when):
                self.fresh_journal()
                self.saved()
                tick = [720 if when == 'before' else 0]
                self.journal.adapter.actor_clock = ActorClock(
                    task_id='local-autosave-fixture', package_sha256='a' * 64,
                    started=0, clock=lambda: tick[0])
                actual = self.page.wait_for_timeout
                def wait(milliseconds):
                    value = actual(milliseconds)
                    tick[0] = 720
                    return value
                with patch.object(self.page, 'wait_for_timeout', side_effect=wait):
                    with self.assertRaises(ActorDeadlineReached):
                        self.wait()
                self.assert_no_input()

    def test_external_journal_input_during_wait_refuses(self):
        self.saved()
        actual = self.page.wait_for_timeout
        def wait(milliseconds):
            self.journal.trace.append({'unrelated_input': True})
            return actual(milliseconds)
        with patch.object(self.page, 'wait_for_timeout', side_effect=wait):
            with self.assertRaises(RuntimeError):
                self.wait()
        self.assert_no_input()

    def test_actor_clock_error_propagates_without_wait_or_gui_input(self):
        self.saved()
        failure = RuntimeError('local actor clock refusal')
        self.journal.clock.error = failure
        with patch.object(self.page, 'wait_for_timeout') as wait:
            with self.assertRaises(RuntimeError) as caught:
                self.wait()
        self.assertIs(caught.exception, failure)
        wait.assert_not_called()
        self.assert_no_input()

    def test_original_ref7_seven_files_remain_exact(self):
        root = Path(__file__).resolve().parents[1]
        for name, digest in FROZEN_REF7.items():
            with self.subTest(file=name):
                self.assertEqual(sha256((root / name).read_bytes()).hexdigest(), digest)

    def test_installed_vendor_provenance_bound_in_intent_and_no_skip_authority(self):
        self.saved()
        proof = self.wait()
        intent = json.loads((self.journal.out / 'reference-priority-autosave-002-intent.private.json').read_bytes())
        self.assertEqual(intent['schema'], 'odoo-reference-priority-autosave-intent-v8')
        self.assertEqual(proof['schema'], 'odoo-reference-priority-autosave-result-v8')
        self.assertEqual(intent['policy'], reference.POLICY)
        self.assertEqual(intent['policy']['installed_priority_field_sha256'],
                         'ef204300cfac3e1a069fa9d44e81f6ab43d1863fa8d9fac7559ea195683ae15b')
        self.assertEqual(intent['policy']['installed_crm_view_sha256'],
                         '55c7a213bacd6cab3e0ff23a54c0c5b19408a814e0dc92a4686d5b625e67844b')
        self.assertTrue(intent['policy']['installed_priority_autosave_default'])
        self.assertFalse(intent['gui_input_authorized'])
        self.assertFalse(intent['same_action_retry_authorized'])
        self.assertTrue(proof['unchanged_reference7_save_reload_and_independent_sql_readback_still_required'])

    def test_invalid_bounds_and_missing_prior_priority_action_fail_before_intent(self):
        self.saved()
        for value in (0, 31, float('nan'), True):
            with self.subTest(timeout=value), self.assertRaisesRegex(RuntimeError, 'bounds_invalid'):
                self.wait(timeout_seconds=value)
        self.journal.trace = []
        with self.assertRaisesRegex(RuntimeError, 'requires_prior_action'):
            self.wait()
        self.assertFalse(list(self.journal.out.iterdir()))
        self.assert_no_input()


if __name__ == '__main__':
    unittest.main()
